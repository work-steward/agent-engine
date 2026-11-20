import json
import subprocess
from dataclasses import replace
from io import StringIO
from unittest.mock import MagicMock, Mock

import pytest

from examples.inventory.__main__ import main
from examples.inventory.warehouse import Warehouse
from examples.inventory.workflow import ORGANIZATION, operator
from work_steward.authority import Authority


def test_changed_demo_policy_is_not_silently_overwritten(tmp_path, capsys):
    prefix = ["--directory", str(tmp_path)]
    assert main([*prefix, "propose", "receipt"]) == 0
    capsys.readouterr()
    authority = Authority(
        tmp_path / "engine.sqlite",
        organization_id=ORGANIZATION,
        administrators=frozenset({operator()}),
    )
    revision, policy = authority.current_policy()
    authority.configure(
        replace(policy, max_quantity=2), actor=operator(), expected_revision=revision
    )
    assert main([*prefix, "dispatch", "receipt"]) == 2
    assert "Demo policy changed" in json.loads(capsys.readouterr().out)["message"]


def test_warehouse_supervisor_handles_startup_and_termination_failures(tmp_path, monkeypatch):
    from examples.inventory import warehouse

    process = Mock()
    process.stdout = StringIO("")
    process.poll.return_value = 1
    selector = MagicMock()
    selector.__enter__.return_value = selector
    selector.select.return_value = []
    monkeypatch.setattr(warehouse.subprocess, "Popen", lambda *_, **__: process)
    monkeypatch.setattr(warehouse.selectors, "DefaultSelector", lambda: selector)
    supervisor = Warehouse(tmp_path)
    with pytest.raises(RuntimeError, match="timed out"):
        supervisor.start()
    assert supervisor.process is supervisor.log is None
    selector.select.return_value = [True]
    process.stdout = StringIO("")
    with pytest.raises(RuntimeError, match="failed to start"):
        supervisor.start()
    process.stdout = StringIO('{"port":1234}\n')
    process.poll.return_value = None
    process.wait.side_effect = [subprocess.TimeoutExpired("simulator", 5), 0]
    supervisor.start().close()
    process.kill.assert_called_once()
    supervisor.close()


def test_spawn_failure_closes_the_log(tmp_path, monkeypatch):
    from examples.inventory import warehouse

    def fail(*_, **__):
        raise OSError("cannot spawn")

    monkeypatch.setattr(warehouse.subprocess, "Popen", fail)
    supervisor = Warehouse(tmp_path)
    with pytest.raises(OSError, match="cannot spawn"):
        supervisor.start()
    assert supervisor.log is None


@pytest.mark.parametrize("failure", ["timeout", "eof", "wrong-marker"])
def test_fault_harness_rejects_missing_or_invalid_worker_barriers(failure):
    from examples.inventory.scenarios import _expect

    pipe = Mock()
    pipe.poll.return_value = failure != "timeout"
    pipe.recv.return_value = "wrong"
    if failure == "eof":
        pipe.recv.side_effect = EOFError
    with pytest.raises(RuntimeError, match="Worker did not reach"):
        _expect(pipe, "released")


def test_fault_harness_cleans_up_a_worker_when_the_barrier_fails(tmp_path, monkeypatch, capsys):
    from examples.inventory import scenarios

    def fail(*_):
        raise RuntimeError("barrier failed")

    monkeypatch.setattr(scenarios, "_expect", fail)
    assert main(["--directory", str(tmp_path), "run", "--scenario", "crash-before-send"]) == 2
    assert "barrier failed" in json.loads(capsys.readouterr().out)["message"]


def _worker_exits_after_observation(*arguments):
    from examples.inventory.scenarios import _worker

    _worker(*arguments)
    raise SystemExit(1)


def test_old_worker_failure_does_not_erase_a_confirmed_effect(tmp_path, monkeypatch, capsys):
    from examples.inventory import scenarios

    monkeypatch.setattr(scenarios, "_worker", _worker_exits_after_observation)
    assert main(["--directory", str(tmp_path), "run", "--scenario", "safe-retry"]) == 2
    assert "Old sender failed" in json.loads(capsys.readouterr().out)["message"]
    assert main(["--directory", str(tmp_path / "safe-retry"), "inspect", "receipt-001"]) == 0
    assert json.loads(capsys.readouterr().out)["effect"] == "effect_confirmed"


def test_invalid_runtime_settings_are_data_not_commands(tmp_path, capsys):
    (tmp_path / "scenario.json").write_text('{"profile":"unknown","behavior":"apply"}')
    assert main(["--directory", str(tmp_path), "propose", "receipt"]) == 2
    assert json.loads(capsys.readouterr().out)["error"] == "ValueError"


def test_proposal_resumes_after_intent_commit_before_request_preparation(
    tmp_path, monkeypatch, capsys
):
    from work_steward.engine import Engine

    prefix = ["--directory", str(tmp_path)]
    with monkeypatch.context() as patch:

        def stop(*_):
            raise RuntimeError("interrupted before preparation")

        patch.setattr(Engine, "prepare", stop)
        assert main([*prefix, "propose", "receipt"]) == 2
        capsys.readouterr()
    for command in ("propose", "approve", "dispatch"):
        assert main([*prefix, command, "receipt"]) == 0
        detail = json.loads(capsys.readouterr().out)
        assert detail["prepared_request"] is not None
    assert detail["effect"] == "effect_confirmed" and len(detail["attempts"]) == 1
    assert main([*prefix, "refresh"]) == 0
    assert json.loads(capsys.readouterr().out)["quantity"] == 10


def test_unsupported_local_identity_reports_a_clear_error(tmp_path, monkeypatch, capsys):
    from examples.inventory import workflow

    monkeypatch.delattr(workflow.os, "getuid")
    assert main(["--directory", str(tmp_path), "run"]) == 2
    assert "POSIX" in json.loads(capsys.readouterr().out)["message"]


@pytest.mark.parametrize("filename", ["engine.sqlite", "warehouse.sqlite"])
def test_unrelated_database_files_are_not_adopted_by_the_demo(tmp_path, capsys, filename):
    original = b"unrelated fixture; do not modify"
    (tmp_path / filename).write_bytes(original)
    assert main(["--directory", str(tmp_path), "propose", "receipt"]) == 2
    assert "fresh directory" in json.loads(capsys.readouterr().out)["message"]
    assert (tmp_path / filename).read_bytes() == original
