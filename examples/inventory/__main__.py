import argparse
import json
import sqlite3
from pathlib import Path

from work_steward.authority import Authority
from work_steward.canonical import canonical_bytes, closed_object, parse_json
from work_steward.engine import Engine
from work_steward.model import Idempotency
from work_steward.simulator.store import Behavior
from work_steward.transport import Endpoint

from .scenarios import SCENARIOS, run
from .warehouse import Warehouse
from .workflow import ORGANIZATION, WAREHOUSE, Inventory, operation_id, operator


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Local synthetic inventory; no credentials or model API needed"
    )
    parser.add_argument("--directory", type=Path, default=Path(".scratch/inventory"))
    subcommands = parser.add_subparsers(dest="command", required=True)
    demo = subcommands.add_parser("run", help="Run a scripted approval and fault scenario")
    demo.add_argument("--scenario", choices=SCENARIOS, default="success")
    proposal = subcommands.add_parser("propose")
    proposal.add_argument("request_id")
    proposal.add_argument("--quantity", type=int, default=10)
    subcommands.add_parser("refresh", help="Refresh inventory evidence from the warehouse")
    for name in ("approve", "dispatch", "reconcile", "retry", "recover", "cancel", "inspect"):
        subcommands.add_parser(name).add_argument("request_id")
    args = parser.parse_args(argv)
    try:
        directory = args.directory.resolve()
        if args.command == "run":
            directory /= args.scenario
        directory.mkdir(parents=True, exist_ok=True)
        actor = operator()
        if args.command == "inspect":
            if not (directory / "engine.sqlite").is_file():
                raise KeyError("No inventory state in this directory")
            authority = Authority(
                directory / "engine.sqlite",
                organization_id=ORGANIZATION,
                administrators=frozenset({actor}),
            )
            print(json.dumps(Engine(authority).inspect(operation_id(args.request_id)), indent=2))
            return 0
        settings_path = directory / "scenario.json"
        if settings_path.exists():
            settings = closed_object(
                parse_json(settings_path.read_bytes()), {"profile", "behavior"}
            )
            Idempotency(settings["profile"])
            Behavior(settings["behavior"])
        else:
            if any((directory / name).exists() for name in ("engine.sqlite", "warehouse.sqlite")):
                raise ValueError(
                    "Existing runtime data has no demo metadata; choose a fresh directory"
                )
            scenario = args.scenario if args.command == "run" else "manual"
            settings = {
                "profile": "none" if scenario == "unknown" else "permanent",
                "behavior": "drop_after_apply" if scenario == "lost-response" else "apply",
            }
            settings_path.write_bytes(canonical_bytes(settings))
        authority = Authority(
            directory / "engine.sqlite",
            organization_id=ORGANIZATION,
            administrators=frozenset({actor}),
        )
        binding = Engine.configuration(authority)
        with Warehouse(directory, port=binding["port"] if binding else 0, **settings) as warehouse:
            engine = Engine(authority, endpoint=Endpoint(warehouse.port), account=WAREHOUSE)
            workflow = Inventory(engine, actor=actor)
            workflow.setup()
            if args.command == "run":
                result = run(workflow, args.scenario)
            elif args.command == "propose":
                workflow.propose(args.request_id, args.quantity)
                result = workflow.report(args.request_id)
            elif args.command == "refresh":
                result = workflow.refresh()
            else:
                identity = operation_id(args.request_id)
                if args.command == "approve":
                    workflow.approve(args.request_id)
                elif args.command == "retry":
                    engine.dispatch(identity, actor=actor, repeat=True)
                else:
                    getattr(engine, args.command)(identity, actor=actor)
                result = workflow.report(args.request_id)
            print(json.dumps(result, indent=2))
        return 0
    except (ValueError, KeyError, RuntimeError, OSError, sqlite3.Error) as error:
        print(json.dumps({"error": type(error).__name__, "message": str(error)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
