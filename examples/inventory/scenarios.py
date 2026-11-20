"""Deterministic fault schedules for the example, outside production control paths."""

import multiprocessing

from work_steward.authority import Authority, AuthorizationDenied
from work_steward.engine import Engine
from work_steward.model import Effect, TransitionError

from .workflow import ORGANIZATION, SKU, operation_id

SCENARIOS = (
    "success",
    "duplicate",
    "revocation",
    "stale-evidence",
    "lost-response",
    "unsafe-retry",
    "crash-before-send",
    "crash-after-send",
    "safe-retry",
    "unknown",
)


def _expect(pipe, marker: str):
    try:
        if pipe.poll(15) and pipe.recv() == marker:
            return
    except EOFError:
        pass
    raise RuntimeError(f"Worker did not reach {marker}")


def _worker(database, actor, identity, point, pipe):
    authority = Authority(database, organization_id=ORGANIZATION, administrators=frozenset({actor}))
    engine = Engine(authority)
    name = {"admitted": "_release", "released": "_transmit", "received": "_receive"}[point]
    original = getattr(engine, name)

    def barrier(*args, **kwargs):
        pipe.send(point)
        pipe.recv()
        return original(*args, **kwargs)

    setattr(engine, name, barrier)
    engine.dispatch(identity, actor=actor)
    pipe.send("finished")


def run(workflow, scenario: str, request_id: str = "receipt-001") -> dict:
    engine, actor = workflow.engine, workflow.actor
    action = workflow.propose(request_id, 10, conditional=scenario != "unsafe-retry")
    checkpoints = []
    if action.effect is not Effect.CONFIRMED:
        workflow.approve(request_id)
        identity = operation_id(request_id)
        if scenario == "unsafe-retry":
            checkpoints.append(
                action.effect.value
                if action.attempts
                else engine.dispatch(identity, actor=actor).effect.value
            )
            try:
                engine.dispatch(identity, actor=actor, repeat=True)
            except TransitionError:
                checkpoints.append("unsafe_retry_blocked")
        elif scenario in {"crash-before-send", "crash-after-send", "safe-retry", "unknown"}:
            point = {
                "crash-before-send": "admitted",
                "crash-after-send": "received",
                "safe-retry": "released",
                "unknown": "released",
            }[scenario]
            context = multiprocessing.get_context("spawn")
            parent, child = context.Pipe()
            worker = context.Process(
                target=_worker, args=(engine.ledger.path, actor, identity, point, child)
            )
            worker.start()
            child.close()
            try:
                _expect(parent, point)
                if scenario != "safe-retry":
                    worker.kill()
                    worker.join(timeout=5)
                engine.recover(identity, actor=actor)
                if scenario == "crash-before-send":
                    engine.dispatch(identity, actor=actor)
                else:
                    checkpoints.append(engine.reconcile(identity, actor=actor).effect.value)
                    if scenario == "safe-retry":
                        engine.dispatch(identity, actor=actor, repeat=True)
                        parent.send("resume")
                        _expect(parent, "finished")
                        worker.join(timeout=5)
                        if worker.exitcode != 0:
                            raise RuntimeError("Old sender failed")
                    elif scenario == "unknown":
                        try:
                            engine.dispatch(identity, actor=actor, repeat=True)
                        except TransitionError:
                            checkpoints.append("unsafe_retry_blocked")
            finally:
                parent.close()
                if worker.is_alive():
                    worker.kill()
                worker.join(timeout=5)
                worker.close()
        elif scenario in {"revocation", "stale-evidence"}:
            if scenario == "revocation":
                grant = workflow.report(request_id)["approvals"][-1]["approval_id"]
                workflow.authority.revoke(grant, actor=actor, reason="Demo withdrawal")
            else:
                workflow.propose("another-receipt", 1)
                workflow.approve("another-receipt")
                engine.dispatch(operation_id("another-receipt"), actor=actor)
                workflow.refresh()
            try:
                engine.dispatch(identity, actor=actor)
            except AuthorizationDenied:
                checkpoints.append("dispatch_blocked")
        else:
            checkpoints.append(engine.dispatch(identity, actor=actor).effect.value)
            if scenario == "lost-response":
                engine.reconcile(identity, actor=actor)
            elif scenario == "duplicate":
                workflow.propose(request_id, 10)
                engine.dispatch(identity, actor=actor)
    report = workflow.report(request_id)
    return {
        "scenario": scenario,
        "operation_id": action.intent.operation_id,
        "effect": report["effect"],
        "reconciliation": report["reconciliation"],
        "attempts": len(report["attempts"]),
        "checkpoints": checkpoints,
        "stock": engine.inventory(SKU, actor=actor),
        "inspect": request_id,
    }
