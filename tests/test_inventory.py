import json
import subprocess
import sys

import pytest

from examples.inventory.__main__ import main
from examples.inventory.scenarios import SCENARIOS


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_business_scenarios_use_engine_and_independent_warehouse(tmp_path, capsys, scenario):
    assert main(["--directory", str(tmp_path), "run", "--scenario", scenario]) == 0
    result = json.loads(capsys.readouterr().out)
    if scenario in {"revocation", "stale-evidence"}:
        assert result["effect"] == "not_attempted"
        assert result["attempts"] == 0
        assert "dispatch_blocked" in result["checkpoints"]
        assert result["stock"]["quantity"] == int(scenario == "stale-evidence")
    elif scenario in {"unknown", "unsafe-retry"}:
        assert result["effect"] == "unknown"
        assert result["stock"]["quantity"] == (10 if scenario == "unsafe-retry" else 0)
        assert "unsafe_retry_blocked" in result["checkpoints"]
        assert result["attempts"] == 1
    else:
        assert result["effect"] == "effect_confirmed"
        assert result["stock"]["quantity"] == 10
        assert result["attempts"] == (2 if scenario in {"safe-retry", "crash-before-send"} else 1)
        if scenario == "lost-response":
            assert result["checkpoints"] == ["unknown"]
    if scenario == "safe-retry":
        assert result["checkpoints"] == ["unknown"]
    assert main(["--directory", str(tmp_path / scenario), "inspect", "receipt-001"]) == 0
    detail = json.loads(capsys.readouterr().out)
    assert detail["history"][-1]["version"] == detail["version"]
    assert detail["approvals"][-1]["request_digest"] == detail["prepared_request"]["digest"]
    assert all(entry["assessment"] != "not_attempted" for entry in detail["observations"])
    if scenario == "unsafe-retry":
        assert detail["intent"]["consistency"] == "C0"
        assert detail["intent"]["resource_version"] is None
        assert detail["responses"][0]["transport_error"] == "transport_unavailable"


def test_lost_unkeyed_response_blocks_retry_until_receipt_reconciliation(tmp_path, capsys):
    prefix = ["--directory", str(tmp_path)]
    for _ in range(2):
        assert main([*prefix, "run", "--scenario", "unsafe-retry"]) == 0
        result = json.loads(capsys.readouterr().out)
        assert result["checkpoints"] == ["unknown", "unsafe_retry_blocked"]
        assert result["attempts"] == 1 and result["stock"]["quantity"] == 10
    prefix = ["--directory", str(tmp_path / "unsafe-retry")]
    assert main([*prefix, "retry", "receipt-001"]) == 2
    assert json.loads(capsys.readouterr().out)["error"] == "TransitionError"
    assert main([*prefix, "propose", "receipt-001"]) == 2
    assert json.loads(capsys.readouterr().out)["error"] == "LedgerConflict"
    assert main([*prefix, "reconcile", "receipt-001"]) == 0
    detail = json.loads(capsys.readouterr().out)
    assert detail["effect"] == "effect_confirmed" and len(detail["attempts"]) == 1
    assert main([*prefix, "refresh"]) == 0
    assert json.loads(capsys.readouterr().out)["quantity"] == 10


def test_existing_proposal_cannot_drop_its_version_condition(tmp_path, capsys):
    from examples.inventory.workflow import ORGANIZATION, Inventory, operator
    from work_steward.authority import Authority
    from work_steward.canonical import ValidationError
    from work_steward.engine import Engine
    from work_steward.ledger import LedgerConflict

    assert main(["--directory", str(tmp_path), "propose", "receipt"]) == 0
    capsys.readouterr()
    authority = Authority(
        tmp_path / "engine.sqlite",
        organization_id=ORGANIZATION,
        administrators=frozenset({operator()}),
    )
    workflow = Inventory(Engine(authority), actor=operator())
    with pytest.raises(LedgerConflict):
        workflow.propose("receipt", 10, conditional=False)
    with pytest.raises(ValidationError, match="boolean"):
        workflow.propose("receipt", 10, conditional="false")


def test_cli_manual_approval_and_repeat_submission(tmp_path, capsys):
    prefix = ["--directory", str(tmp_path)]
    assert main([*prefix, "propose", "stock-receipt", "--quantity", "7"]) == 0
    first = json.loads(capsys.readouterr().out)
    assert first["approvals"] == first["attempts"] == []
    assert main([*prefix, "dispatch", "stock-receipt"]) == 2
    assert json.loads(capsys.readouterr().out)["error"] == "AuthorizationDenied"
    assert main([*prefix, "propose", "stock-receipt", "--quantity", "8"]) == 2
    assert json.loads(capsys.readouterr().out)["error"] == "LedgerConflict"
    for command in ("approve", "dispatch", "reconcile", "propose"):
        arguments = [*prefix, command, "stock-receipt"]
        if command == "propose":
            arguments += ["--quantity", "7"]
        assert main(arguments) == 0
        detail = json.loads(capsys.readouterr().out)
        assert detail["intent"]["operation_id"] == first["intent"]["operation_id"]
    assert detail["effect"] == "effect_confirmed" and len(detail["attempts"]) == 1
    assert main([*prefix, "run"]) == 0
    capsys.readouterr()
    assert main([*prefix, "run"]) == 0
    assert json.loads(capsys.readouterr().out)["stock"]["quantity"] == 10


def test_cli_cancel_recover_and_errors(tmp_path, capsys):
    prefix = ["--directory", str(tmp_path)]
    assert main([*prefix, "inspect", "absent"]) == 2
    capsys.readouterr()
    assert main([*prefix, "propose", "receipt"]) == 0
    capsys.readouterr()
    assert main([*prefix, "reconcile", "receipt"]) == 2
    capsys.readouterr()
    for command in ("recover", "cancel", "cancel"):
        assert main([*prefix, command, "receipt"]) == 0
        capsys.readouterr()
    assert main([*prefix, "retry", "receipt"]) == 2
    assert json.loads(capsys.readouterr().out)["error"] == "TransitionError"


def test_module_entrypoint_needs_no_external_service_or_keys(tmp_path):
    # Fixed Python module; all options are local synthetic data.
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-m", "examples.inventory", "--directory", str(tmp_path), "run"],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert json.loads(result.stdout)["effect"] == "effect_confirmed"


def test_cli_cannot_approve_an_adjustment_above_the_business_limit(tmp_path, capsys):
    prefix = ["--directory", str(tmp_path)]
    assert main([*prefix, "propose", "too-large", "--quantity", "101"]) == 0
    capsys.readouterr()
    assert main([*prefix, "approve", "too-large"]) == 2
    assert json.loads(capsys.readouterr().out)["error"] == "AuthorizationDenied"
    assert main([*prefix, "inspect", "too-large"]) == 0
    assert json.loads(capsys.readouterr().out)["attempts"] == []
