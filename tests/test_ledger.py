"""Engine storage tests; no test here authorizes or invokes effectful transport."""

import multiprocessing
import sqlite3
from contextlib import contextmanager
from dataclasses import replace

import pytest

from work_steward.canonical import ValidationError, parse_json
from work_steward.intent import Consistency, Intent
from work_steward.ledger import (
    Command,
    Ledger,
    LedgerConflict,
    LedgerFormatError,
    OperationNotFound,
)
from work_steward.ledger_schema import APPLICATION_ID, SCHEMA_VERSION
from work_steward.model import (
    Disposition,
    Effect,
    Idempotency,
    Observation,
    Phase,
    Reconciliation,
    RepetitionProof,
    TransitionError,
)


@pytest.fixture
def ledger(tmp_path):
    return Ledger(tmp_path / "engine.sqlite", organization_id="org-1")


def apply(ledger, action, command, **arguments):
    return ledger.apply(
        action.intent.operation_id, expected_version=action.version, command=command, **arguments
    )


def admitted(ledger, intent):
    action = ledger.submit(intent, provider_key="key-1", idempotency=Idempotency.PERMANENT)
    action = apply(ledger, action, Command.EVALUATE)
    return apply(ledger, action, Command.ADMIT, attempt_id="attempt-1", generation=0)


def possibly_sent(ledger, intent):
    action = admitted(ledger, intent)
    return apply(ledger, action, Command.SEND_POSSIBLE, attempt_id="attempt-1", generation=0)


def observation(intent, assessment=Effect.CONFIRMED, **changes):
    return Observation(
        **{
            "observation_id": "obs-1",
            "attempt_id": "attempt-1",
            "intent_digest": intent.intent_digest,
            "assessment": assessment,
            "provider_effect_id": "effect-1",
            **changes,
        }
    )


def counts(path):
    with sqlite3.connect(path) as db:
        return tuple(
            db.execute(sql).fetchone()[0]
            for sql in (
                "SELECT count(*) FROM operations",
                "SELECT count(*) FROM reservations",
                "SELECT count(*) FROM action_state",
                "SELECT count(*) FROM attempts",
                "SELECT count(*) FROM observations",
                "SELECT count(*) FROM journal",
            )
        )


def test_ac02_identical_submission_returns_current_state_without_a_new_event(ledger, intent):
    original = ledger.submit(intent, provider_key="key-1")
    current = apply(ledger, original, Command.STOP, close=True)
    reopened = Ledger(ledger.path, organization_id="org-1")
    assert reopened.submit(intent, provider_key="key-1") == current
    assert current.disposition is Disposition.CLOSED
    assert counts(ledger.path) == (1, 1, 1, 0, 0, 2)
    assert reopened.reservation("sim.resource", "event-1") == "op-1"
    assert reopened.reservation("sim.resource", "missing") is None


@pytest.mark.parametrize(
    "changes",
    [
        {"quantity": 2},
        {"account": "other"},
        {"resource": "other"},
        {"business_effect_key": "other"},
        {"execution_id": "other"},
        {"adapter_digest": "b" * 64},
    ],
)
def test_operation_identity_cannot_bind_changed_intent(ledger, intent, changes):
    original = ledger.submit(intent, provider_key="key-1")
    with pytest.raises(LedgerConflict, match="immutable binding"):
        ledger.submit(replace(intent, **changes), provider_key="key-1")
    assert ledger.get("op-1") == original
    assert counts(ledger.path) == (1, 1, 1, 0, 0, 1)


@pytest.mark.parametrize(
    "changes",
    [
        {"provider_key": "key-2"},
        {"idempotency": Idempotency.PERMANENT},
        {"supported_consistency": frozenset({Consistency.C0})},
        {"max_attempts": 4},
    ],
)
def test_operation_profile_cannot_be_reinterpreted_on_restart(ledger, intent, changes):
    ledger.submit(intent, provider_key="key-1")
    with pytest.raises(LedgerConflict):
        Ledger(ledger.path, organization_id="org-1").submit(
            intent, **{"provider_key": "key-1", **changes}
        )
    assert counts(ledger.path) == (1, 1, 1, 0, 0, 1)


@pytest.mark.parametrize(
    "ending", ["closed_unsent", "revoked", "unknown", "confirmed", "no_effect"]
)
def test_ac09_reservation_survives_lifecycle_and_restart(ledger, intent, ending):
    if ending == "closed_unsent":
        action = apply(ledger, admitted(ledger, intent), Command.STOP, close=True)
    elif ending == "revoked":
        action = apply(
            ledger,
            admitted(ledger, intent),
            Command.SET_AUTHORITY,
            authorized=False,
            evidence_valid=True,
        )
    else:
        action = apply(ledger, possibly_sent(ledger, intent), Command.STOP, close=True)
        if ending != "unknown":
            assessment = Effect.CONFIRMED if ending == "confirmed" else Effect.NO_EFFECT
            action = apply(
                ledger, action, Command.OBSERVE, observation=observation(intent, assessment)
            )
    restarted = Ledger(ledger.path, organization_id="org-1")
    assert restarted.get("op-1") == action
    assert (
        restarted.submit(intent, provider_key="key-1", idempotency=Idempotency.PERMANENT) == action
    )
    with pytest.raises(LedgerConflict, match="permanently reserved"):
        restarted.submit(replace(intent, operation_id="other"), provider_key="key-2")
    assert (
        restarted.reservation(intent.business_effect_namespace, intent.business_effect_key)
        == "op-1"
    )
    with pytest.raises(OperationNotFound):
        restarted.get("other")


def test_key_scopes_and_failed_provider_binding_leave_no_reservation(ledger, intent):
    ledger.submit(intent, provider_key="key-1")
    independent = replace(intent, operation_id="op-2", business_effect_namespace="another")
    with pytest.raises(LedgerConflict, match="Provider key"):
        ledger.submit(independent, provider_key="key-1")
    assert ledger.reservation("another", "event-1") is None
    ledger.submit(independent, provider_key="key-2")
    ledger.submit(
        replace(intent, operation_id="op-3", business_effect_key="event-2", account="other"),
        provider_key="key-1",
    )
    assert counts(ledger.path) == (3, 3, 3, 0, 0, 3)


def test_ac10_attempts_evidence_and_journal_round_trip(ledger, intent):
    action = possibly_sent(ledger, intent)
    action = apply(ledger, action, Command.TAKEOVER)
    action = apply(ledger, action, Command.BEGIN_RECONCILIATION, authorized=True)
    claim = observation(intent)
    action = apply(ledger, action, Command.OBSERVE, observation=claim)
    restarted = Ledger(ledger.path, organization_id="org-1")
    assert restarted.get("op-1") == action
    assert action.effect is Effect.CONFIRMED
    assert action.disposition is Disposition.CLOSED
    assert action.attempts[0].phase is Phase.POSSIBLY_SENT
    assert action.observations == (claim,)
    assert counts(ledger.path) == (1, 1, 1, 1, 1, 7)
    entries = restarted.history("op-1")
    assert [entry.command for entry in entries] == [
        "submit",
        "evaluate",
        "admit",
        "send_possible",
        "takeover",
        "begin_reconciliation",
        "observe",
    ]
    assert [entry.previous_version for entry in entries] == [None, 0, 1, 2, 3, 4, 5]
    assert [entry.version for entry in entries] == list(range(7))
    assert entries[-1].effect is Effect.CONFIRMED
    assert parse_json(entries[-1].data)["observation"]["provider_effect_id"] == "effect-1"
    assert apply(restarted, action, Command.OBSERVE, observation=claim) == action
    assert restarted.history("op-1") == entries
    conflict = replace(claim, assessment=Effect.NO_EFFECT)
    action = apply(restarted, action, Command.OBSERVE, observation=conflict)
    assert restarted.get("op-1").observations == (claim, conflict)
    assert action.effect is Effect.CONFLICTING
    assert action.reconciliation is Reconciliation.HUMAN


def test_permanent_key_repetition_coverage_is_persisted(ledger, intent):
    action = apply(ledger, possibly_sent(ledger, intent), Command.TAKEOVER)
    proof = RepetitionProof(
        intent.intent_digest, frozenset({"attempt-1"}), intent.account, intent.capability, "key-1"
    )
    action = apply(
        ledger,
        action,
        Command.ADMIT,
        attempt_id="attempt-2",
        generation=action.generation,
        proof=proof,
    )
    restarted = Ledger(ledger.path, organization_id="org-1")
    assert restarted.get("op-1") == action
    assert action.attempts[-1].repetition_covered == frozenset({"attempt-1"})
    assert parse_json(restarted.history("op-1")[-1].data)["proof"]["covered_attempt_ids"] == [
        "attempt-1"
    ]


def test_stale_updates_and_unknown_retry_do_not_change_the_database(ledger, intent):
    action = possibly_sent(ledger, intent)
    other = Ledger(ledger.path, organization_id="org-1")
    action = apply(ledger, action, Command.TAKEOVER)
    history = ledger.history("op-1")
    with pytest.raises(TransitionError, match="Stale"):
        other.apply("op-1", expected_version=2, command=Command.STOP, close=True)
    with pytest.raises(TransitionError, match="safe-repetition"):
        apply(other, action, Command.ADMIT, attempt_id="attempt-2", generation=action.generation)
    with pytest.raises(TransitionError, match="Stale worker"):
        apply(other, action, Command.ADMIT, attempt_id="attempt-2", generation=0)
    assert other.get("op-1") == action
    assert other.history("op-1") == history


@pytest.mark.parametrize("transition", [False, True])
def test_ac10_sql_failure_rolls_back_every_part_of_the_command(ledger, intent, transition):
    if transition:
        before = apply(ledger, ledger.submit(intent, provider_key="key-1"), Command.EVALUATE)
    initial_counts = counts(ledger.path)
    with sqlite3.connect(ledger.path) as db:
        db.execute("""CREATE TRIGGER fail_journal BEFORE INSERT ON journal
                      BEGIN SELECT RAISE(ABORT,'injected storage failure'); END""")
    with pytest.raises(sqlite3.IntegrityError, match="injected storage failure"):
        if transition:
            apply(ledger, before, Command.ADMIT, attempt_id="attempt-1", generation=0)
        else:
            ledger.submit(intent, provider_key="key-1")
    assert counts(ledger.path) == initial_counts
    if transition:
        assert ledger.get("op-1") == before
    else:
        assert ledger.reservation("sim.resource", "event-1") is None


def test_busy_database_denies_submission_without_partial_registration(ledger, intent):
    constrained = Ledger(ledger.path, organization_id="org-1", busy_timeout_ms=20)
    with sqlite3.connect(ledger.path, isolation_level=None) as db:
        db.execute("BEGIN IMMEDIATE")
        try:
            with pytest.raises(sqlite3.OperationalError, match="locked"):
                constrained.submit(intent, provider_key="key-1")
        finally:
            db.rollback()
    assert counts(ledger.path) == (0, 0, 0, 0, 0, 0)


def test_evidence_and_attempt_assessments_roll_back_with_failed_journal(ledger, intent):
    before = possibly_sent(ledger, intent)
    with sqlite3.connect(ledger.path) as db:
        db.execute("""CREATE TRIGGER fail_observation BEFORE INSERT ON journal
                      WHEN NEW.command='observe'
                      BEGIN SELECT RAISE(ABORT,'injected storage failure'); END""")
    with pytest.raises(sqlite3.IntegrityError, match="injected storage failure"):
        apply(ledger, before, Command.OBSERVE, observation=observation(intent))
    assert ledger.get("op-1") == before
    assert counts(ledger.path) == (1, 1, 1, 1, 0, 4)
    assert ledger.history("op-1")[-1].effect is Effect.UNKNOWN


def test_authority_command_commits_its_combined_version_and_fence(ledger, intent):
    before = admitted(ledger, intent)
    after = apply(ledger, before, Command.SET_AUTHORITY, authorized=False, evidence_valid=False)
    assert after.version == before.version + 2
    assert ledger.get("op-1") == after
    assert after.attempts[0].phase is Phase.UNSENT
    assert after.generation == before.generation + 1
    entry = ledger.history("op-1")[-1]
    assert (entry.previous_version, entry.version) == (before.version, after.version)
    assert parse_json(entry.data) == {"authorized": False, "evidence_valid": False}


def test_long_journal_is_not_limited_by_the_repetition_proof_collection_bound(ledger, intent):
    action = possibly_sent(ledger, intent)
    for number in range(70):
        action = apply(
            ledger,
            action,
            Command.OBSERVE,
            observation=observation(intent, Effect.UNKNOWN, observation_id=f"poll-{number}"),
        )
    assert Ledger(ledger.path, organization_id="org-1").get("op-1") == action
    assert len(ledger.history("op-1")) == 74
    assert action.effect is Effect.UNKNOWN


def test_database_identity_does_not_depend_on_later_working_directory(
    tmp_path, intent, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    store = Ledger("engine.sqlite", organization_id="org-1")
    original = store.submit(intent, provider_key="key-1")
    directory = tmp_path / "elsewhere"
    directory.mkdir()
    monkeypatch.chdir(directory)
    assert store.get("op-1") == original
    assert not (directory / "engine.sqlite").exists()


def test_schema_durability_identity_and_retention_guards(ledger, intent):
    action = admitted(ledger, intent)
    with ledger._transaction() as db:
        assert db.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert db.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        assert db.execute("PRAGMA synchronous").fetchone()[0] == 2
        assert db.execute("PRAGMA busy_timeout").fetchone()[0] == 2000
        assert db.execute("PRAGMA application_id").fetchone()[0] == APPLICATION_ID
        assert db.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
        assert all(
            row["strict"]
            for row in db.execute("PRAGMA table_list")
            if row["name"] not in ("sqlite_schema", "sqlite_temp_schema")
        )
        for sql in (
            "DELETE FROM reservations",
            "UPDATE operations SET provider_key='changed'",
            "DELETE FROM operations",
            "DELETE FROM action_state",
            "DELETE FROM journal",
            "DELETE FROM attempts",
            "UPDATE attempts SET generation=9",
        ):
            with pytest.raises(sqlite3.IntegrityError):
                db.execute(sql)
    assert ledger.get("op-1") == action
    with pytest.raises(LedgerFormatError, match="another organization"):
        Ledger(ledger.path, organization_id="other")
    with pytest.raises(ValidationError):
        ledger.submit(replace(intent, organization_id="other"), provider_key="key-1")


def test_unrecognized_database_and_newer_schema_are_rejected(tmp_path, ledger):
    foreign = tmp_path / "foreign.sqlite"
    with sqlite3.connect(foreign) as db:
        db.execute("CREATE TABLE external_data (id INTEGER)")
    with pytest.raises(LedgerFormatError):
        Ledger(foreign, organization_id="org-1")
    with sqlite3.connect(foreign) as db:
        assert db.execute("SELECT name FROM sqlite_schema WHERE type='table'").fetchall() == [
            ("external_data",)
        ]
        assert db.execute("PRAGMA journal_mode").fetchone()[0] == "delete"
    with sqlite3.connect(ledger.path) as db:
        db.execute("PRAGMA user_version=2")
    with pytest.raises(LedgerFormatError):
        Ledger(ledger.path, organization_id="org-1")
    with pytest.raises(LedgerFormatError):
        ledger.get("absent")


def test_closed_commands_and_input_limits_fail_without_writes(ledger, intent):
    with pytest.raises(OperationNotFound):
        ledger.get("absent")
    with pytest.raises(OperationNotFound):
        ledger.history("absent")
    with pytest.raises(ValidationError):
        ledger.submit(intent, provider_key="key-1", max_attempts=65)
    action = ledger.submit(intent, provider_key="key-1")
    with pytest.raises(ValidationError):
        apply(ledger, action, "evaluate")
    with pytest.raises(ValidationError):
        ledger.apply("op-1", expected_version=True, command=Command.STOP)
    with pytest.raises(TypeError):
        apply(ledger, action, Command.STOP, snapshot={})
    assert counts(ledger.path) == (1, 1, 1, 0, 0, 1)
    with pytest.raises(ValidationError):
        Ledger(":memory:", organization_id="org-1")


@contextmanager
def process(target, *arguments):
    context = multiprocessing.get_context("spawn")
    parent, child = context.Pipe()
    worker = context.Process(target=target, args=(*arguments, child))
    worker.start()
    child.close()
    try:
        yield worker, parent
    finally:
        parent.close()
        if worker.is_alive():
            worker.kill()
        worker.join(timeout=10)
        assert not worker.is_alive()
        worker.close()


def receive(connection):
    assert connection.poll(10), "Worker did not reach its explicit synchronization barrier"
    return connection.recv()


def _crashing_writer(path, intent_bytes, command, before_commit, connection):
    class BarrierLedger(Ledger):
        @staticmethod
        def _journal(db, *arguments):
            Ledger._journal(db, *arguments)
            if before_commit:
                connection.send("uncommitted")
                connection.recv()

    intent = Intent.from_json(intent_bytes)
    store = BarrierLedger(path, organization_id="org-1")
    if command == "admit":
        store.apply(
            "op-1", expected_version=1, command=Command.ADMIT, attempt_id="attempt-1", generation=0
        )
    elif command == "send_possible":
        store.apply(
            "op-1",
            expected_version=2,
            command=Command.SEND_POSSIBLE,
            attempt_id="attempt-1",
            generation=0,
        )
    elif command == "observe":
        store.apply(
            "op-1", expected_version=3, command=Command.OBSERVE, observation=observation(intent)
        )
    else:
        store.submit(intent, provider_key="key-1")
    connection.send("committed")
    connection.recv()


@pytest.mark.parametrize("command", ["submit", "admit", "send_possible", "observe"])
@pytest.mark.parametrize("before_commit", [False, True])
def test_real_process_death_preserves_atomic_registration_attempt_or_evidence(
    ledger,
    intent,
    command,
    before_commit,
):
    if command == "admit":
        apply(ledger, ledger.submit(intent, provider_key="key-1"), Command.EVALUATE)
    elif command == "send_possible":
        admitted(ledger, intent)
    elif command == "observe":
        possibly_sent(ledger, intent)
    before_counts = {
        "submit": (0, 0, 0, 0, 0, 0),
        "admit": (1, 1, 1, 0, 0, 2),
        "send_possible": (1, 1, 1, 1, 0, 3),
        "observe": (1, 1, 1, 1, 0, 4),
    }
    after_counts = {
        "submit": (1, 1, 1, 0, 0, 1),
        "admit": (1, 1, 1, 1, 0, 3),
        "send_possible": (1, 1, 1, 1, 0, 4),
        "observe": (1, 1, 1, 1, 1, 5),
    }
    expected_counts = before_counts[command] if before_commit else after_counts[command]
    with process(_crashing_writer, ledger.path, intent.canonical, command, before_commit) as (
        worker,
        connection,
    ):
        assert receive(connection) == ("uncommitted" if before_commit else "committed")
        # An independent connection sees all or none of the command's writes.
        assert counts(ledger.path) == expected_counts
        worker.kill()
        worker.join(timeout=10)
    restarted = Ledger(ledger.path, organization_id="org-1")
    assert counts(ledger.path) == expected_counts
    if before_commit and command == "submit":
        with pytest.raises(OperationNotFound):
            restarted.get("op-1")
        assert restarted.reservation("sim.resource", "event-1") is None
    else:
        action = restarted.get("op-1")
        assert len(action.attempts) == expected_counts[3]
        assert len(action.observations) == expected_counts[4]
        assert action.version == expected_counts[-1] - 1
        assert restarted.reservation("sim.resource", "event-1") == "op-1"
        if command == "send_possible" and not before_commit:
            assert action.effect is Effect.UNKNOWN
            with pytest.raises(TransitionError):
                apply(
                    restarted, action, Command.SEND_POSSIBLE, attempt_id="attempt-1", generation=0
                )
            action = apply(restarted, action, Command.TAKEOVER)
            with pytest.raises(TransitionError):
                apply(
                    restarted,
                    action,
                    Command.ADMIT,
                    attempt_id="attempt-2",
                    generation=action.generation,
                )
        elif command == "observe" and not before_commit:
            assert action.effect is Effect.CONFIRMED


def _racing_writer(path, intent_bytes, scenario, connection):
    store = Ledger(path, organization_id="org-1")
    connection.send("ready")
    connection.recv()
    try:
        if scenario == "stale_update":
            action = store.apply(
                "op-1",
                expected_version=1,
                command=Command.ADMIT,
                attempt_id="attempt-" + str(connection.recv()),
                generation=0,
            )
        else:
            intent = Intent.from_json(intent_bytes)
            key = (
                "same-provider-key"
                if scenario == "provider_conflict"
                else "key-" + intent.operation_id
            )
            action = store.submit(intent, provider_key=key)
        connection.send(("ok", action.intent.operation_id))
    except (LedgerConflict, TransitionError) as error:
        connection.send((type(error).__name__, str(error)))


@pytest.mark.parametrize(
    "scenario",
    [
        "same_submission",
        "business_conflict",
        "provider_conflict",
        "identity_conflict",
        "stale_update",
    ],
)
def test_independent_processes_serialize_competing_writes(ledger, intent, scenario):
    transition = scenario == "stale_update"
    if transition:
        apply(ledger, ledger.submit(intent, provider_key="key-1"), Command.EVALUATE)
    changes = {
        "same_submission": {},
        "business_conflict": {"operation_id": "op-2"},
        "provider_conflict": {"operation_id": "op-2", "business_effect_key": "event-2"},
        "identity_conflict": {"quantity": 2},
        "stale_update": {},
    }
    second = replace(intent, **changes[scenario])
    with (
        process(_racing_writer, ledger.path, intent.canonical, scenario) as (first, pipe1),
        process(_racing_writer, ledger.path, second.canonical, scenario) as (other, pipe2),
    ):
        assert receive(pipe1) == receive(pipe2) == "ready"
        pipe1.send("go")
        pipe2.send("go")
        if transition:
            pipe1.send(1)
            pipe2.send(2)
        results = [receive(pipe1), receive(pipe2)]
        first.join(timeout=10)
        other.join(timeout=10)
        assert first.exitcode == other.exitcode == 0
    statuses = sorted(result[0] for result in results)
    assert statuses == (
        ["ok", "ok"]
        if scenario == "same_submission"
        else ["LedgerConflict", "ok"]
        if not transition
        else ["TransitionError", "ok"]
    )
    assert counts(ledger.path) == ((1, 1, 1, 1, 0, 3) if transition else (1, 1, 1, 0, 0, 1))
    winner = next(result[1] for result in results if result[0] == "ok")
    stored = ledger.get(winner)
    assert ledger.reservation("sim.resource", stored.intent.business_effect_key) == winner


@pytest.mark.parametrize("store_kind", ["engine", "provider"])
def test_unsupported_sqlite_version_denies_open(tmp_path, monkeypatch, store_kind):
    from work_steward.simulator.store import ProviderStore

    monkeypatch.setattr(sqlite3, "sqlite_version_info", (3, 36, 0))
    with pytest.raises(RuntimeError, match=r"3\.37"):
        if store_kind == "engine":
            Ledger(tmp_path / "engine.sqlite", organization_id="org-1")
        else:
            ProviderStore(tmp_path / "provider.sqlite")


@pytest.mark.parametrize("store_kind", ["engine", "provider"])
@pytest.mark.parametrize(
    "blocked", ["PRAGMA journal_mode=WAL", "PRAGMA synchronous", "PRAGMA foreign_keys"]
)
def test_unavailable_durability_settings_deny_open(tmp_path, monkeypatch, store_kind, blocked):
    from work_steward.simulator.store import ProviderStore

    class RestrictedConnection(sqlite3.Connection):
        def execute(self, sql, *arguments):
            if sql == blocked:
                return super().execute("SELECT 'unavailable'")
            return super().execute(sql, *arguments)

    connect = sqlite3.connect
    monkeypatch.setattr(
        sqlite3,
        "connect",
        lambda *args, **kwargs: connect(*args, **kwargs, factory=RestrictedConnection),
    )
    with pytest.raises(RuntimeError, match="unavailable"):
        if store_kind == "engine":
            Ledger(tmp_path / "engine.sqlite", organization_id="org-1")
        else:
            ProviderStore(tmp_path / "provider.sqlite")
