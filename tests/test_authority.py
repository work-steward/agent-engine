import json
import sqlite3
from dataclasses import replace

import pytest
from conftest import process, receive

from work_steward.authority import Authority, AuthorizationDenied, Policy
from work_steward.canonical import ValidationError
from work_steward.intent import Consistency, EvidenceRef
from work_steward.ledger import Command, Ledger, LedgerConflict, LedgerFormatError
from work_steward.ledger_schema import AUTHORITY_IMMUTABLE, DISPATCH_IMMUTABLE, SCHEMA_VERSION
from work_steward.model import Disposition, Effect, Idempotency, Phase, TransitionError


class Clock:
    value = 100

    def __call__(self):
        return self.value


@pytest.fixture
def controller(tmp_path):
    return Authority(
        tmp_path / "governed.sqlite",
        organization_id="org-1",
        administrators=frozenset({"owner"}),
        clock=Clock(),
    )


@pytest.fixture
def policy(intent):
    return Policy(
        intent.account,
        intent.capability,
        intent.adapter_id,
        intent.adapter_digest,
        frozenset({intent.resource}),
        frozenset({"reviewer", "other"}),
        1,
    )


def prepare(controller, policy, intent):
    controller.configure(policy, actor="owner", expected_revision=0)
    return controller.ledger.submit(intent, provider_key="key-1", idempotency=Idempotency.PERMANENT)


def approve(controller, policy, intent):
    prepare(controller, policy, intent)
    return controller.approve("op-1", approval_id="approval-1", actor="reviewer", expires_at=150)


def admit(controller, action, attempt="attempt-1"):
    return controller.admit(
        "op-1", expected_version=action.version, generation=action.generation, attempt_id=attempt
    )


def send(controller, action):
    return controller.mark_send_possible(
        "op-1",
        expected_version=action.version,
        generation=action.generation,
        attempt_id="attempt-1",
    )


def record_evidence(controller, reference, **arguments):
    return controller.record_evidence(
        reference, account="account-1", capability="sim.effect.create", **arguments
    )


def test_approval_is_exact_durable_and_required_at_both_boundaries(controller, policy, intent):
    proposed = controller.ledger.submit(
        intent, provider_key="key-1", idempotency=Idempotency.PERMANENT
    )
    assert not proposed.authorized and not proposed.evidence_valid
    with pytest.raises(AuthorizationDenied, match="No active policy"):
        admit(controller, proposed)
    controller.configure(policy, actor="owner", expected_revision=0)
    with pytest.raises(AuthorizationDenied, match="missing"):
        admit(controller, proposed)
    approved = controller.approve(
        "op-1", approval_id="approval-1", actor="reviewer", expires_at=150
    )
    assert approved.disposition is Disposition.ELIGIBLE
    restarted = Authority(
        controller.ledger.path,
        organization_id="org-1",
        administrators=frozenset({"owner"}),
        clock=lambda: 101,
    )
    current = admit(restarted, approved)
    released = send(restarted, current)
    assert released.effect is Effect.UNKNOWN
    assert released.attempts[0].phase is Phase.POSSIBLY_SENT
    with pytest.raises(TransitionError, match="single-use"):
        send(restarted, released)
    entry = restarted.ledger.history("op-1")[-1]
    assert json.loads(entry.data)["approval_id"] == "approval-1"
    assert restarted.ledger.reservation("sim.resource", "event-1") == "op-1"


@pytest.mark.parametrize("command", list(Command))
def test_reference_commands_cannot_bypass_governed_authority(controller, intent, command):
    controller.ledger.submit(intent, provider_key="key-1")
    with pytest.raises(TransitionError, match="authority controller"):
        controller.ledger.apply("op-1", expected_version=0, command=command)
    with pytest.raises(LedgerFormatError, match="mode"):
        Ledger(controller.ledger.path, organization_id="org-1")


@pytest.mark.parametrize(
    "changes",
    [
        {"account": "other"},
        {"capability": "unsupported"},
        {"adapter_id": "other"},
        {"adapter_digest": "b" * 64},
        {"resources": frozenset({"other"})},
    ],
)
def test_policy_scope_cannot_be_substituted(controller, policy, intent, changes):
    prepare(controller, replace(policy, **changes), intent)
    with pytest.raises(AuthorizationDenied, match="scope"):
        controller.approve("op-1", approval_id="a", actor="reviewer", expires_at=150)
    assert not controller.ledger.get("op-1").authorized


@pytest.mark.parametrize(
    "intent_changes",
    [
        {"quantity": 2},
        {"consistency": Consistency.C2, "resource_version": 0},
    ],
)
def test_policy_quantity_and_capability_limits(controller, policy, intent, intent_changes):
    prepare(controller, policy, replace(intent, **intent_changes))
    with pytest.raises(AuthorizationDenied, match="scope"):
        controller.approve("op-1", approval_id="a", actor="reviewer", expires_at=150)


@pytest.mark.parametrize("expiry", [100, 99, 3701])
def test_approval_lifetime_is_bounded(controller, policy, intent, expiry):
    prepare(controller, policy, intent)
    with pytest.raises(AuthorizationDenied, match="expiry"):
        controller.approve("op-1", approval_id="a", actor="reviewer", expires_at=expiry)


def test_roles_and_revision_checks_restrict_control_calls(controller, policy, intent):
    with pytest.raises(AuthorizationDenied, match="Administrator"):
        controller.configure(policy, actor="reviewer", expected_revision=0)
    prepare(controller, policy, intent)
    with pytest.raises(LedgerConflict, match="Stale policy"):
        controller.configure(policy, actor="owner", expected_revision=0)
    with pytest.raises(AuthorizationDenied, match="Approver"):
        controller.approve("op-1", approval_id="a", actor="owner", expires_at=150)
    with pytest.raises(LedgerConflict, match="Administrator binding"):
        Authority(
            controller.ledger.path,
            organization_id="org-1",
            administrators=frozenset({"imposter"}),
            clock=lambda: 100,
        )


def test_expiry_denial_is_persisted_and_cannot_be_undone_by_clock_rollback(
    controller, policy, intent
):
    action = approve(controller, policy, intent)
    controller._clock.value = 150
    with pytest.raises(AuthorizationDenied, match="expired"):
        admit(controller, action)
    controller._clock.value = 149
    with pytest.raises(AuthorizationDenied, match="backwards"):
        admit(controller, action)
    with sqlite3.connect(controller.ledger.path) as db:
        assert db.execute("SELECT last_tick FROM authority_config").fetchone()[0] == 150
        assert db.execute("SELECT count(*) FROM authority_denials").fetchone()[0] == 1
        assert db.execute("SELECT count(*) FROM attempts").fetchone()[0] == 0


@pytest.mark.parametrize("change", ["expiry", "policy", "evidence"])
def test_admission_does_not_freeze_authority_before_send(controller, policy, intent, change):
    reference = EvidenceRef(intent.resource, "eligible", "v1")
    intent = replace(intent, evidence_refs=(reference,))
    policy = replace(policy, required_evidence=frozenset({"eligible"}))
    record_evidence(controller, reference, actor="owner", expected_revision=0, expires_at=200)
    current = admit(controller, approve(controller, policy, intent))
    if change == "expiry":
        controller._clock.value = 150
    elif change == "policy":
        controller.configure(policy, actor="owner", expected_revision=1)
    else:
        record_evidence(
            controller,
            replace(reference, material_version="v2"),
            actor="owner",
            expected_revision=1,
            expires_at=200,
        )
    with pytest.raises(AuthorizationDenied):
        send(controller, current)
    assert controller.ledger.get("op-1").attempts[0].phase is Phase.ADMITTED


def test_evidence_requirements_cannot_be_omitted_or_rebound(controller, policy, intent):
    reference = EvidenceRef(intent.resource, "eligible", "v1")
    policy = replace(policy, required_evidence=frozenset({"eligible"}))
    prepare(controller, policy, intent)
    with pytest.raises(AuthorizationDenied, match="Required evidence"):
        controller.approve("op-1", approval_id="a", actor="reviewer", expires_at=150)
    another = replace(
        intent, operation_id="op-2", business_effect_key="event-2", evidence_refs=(reference,)
    )
    controller.ledger.submit(another, provider_key="key-2")
    with pytest.raises(AuthorizationDenied, match="Evidence is missing"):
        controller.approve("op-2", approval_id="a", actor="reviewer", expires_at=150)
    record_evidence(controller, reference, actor="owner", expected_revision=0, expires_at=120)
    with pytest.raises(LedgerConflict, match="Stale evidence"):
        record_evidence(controller, reference, actor="owner", expected_revision=0, expires_at=120)
    controller._clock.value = 120
    with pytest.raises(AuthorizationDenied, match="expired"):
        controller.approve("op-2", approval_id="a", actor="reviewer", expires_at=150)
    with pytest.raises(AuthorizationDenied, match="already expired"):
        record_evidence(controller, reference, actor="owner", expected_revision=1, expires_at=120)


@pytest.mark.parametrize("wrong_scope", [{"account": "other"}, {"capability": "other"}])
def test_evidence_cannot_cross_account_or_capability_scopes(
    controller, policy, intent, wrong_scope
):
    reference = EvidenceRef(intent.resource, "eligible", "v1")
    scope = {"account": intent.account, "capability": intent.capability, **wrong_scope}
    controller.record_evidence(
        reference, **scope, actor="owner", expected_revision=0, expires_at=200
    )
    prepare(
        controller,
        replace(policy, required_evidence=frozenset({"eligible"})),
        replace(intent, evidence_refs=(reference,)),
    )
    with pytest.raises(AuthorizationDenied, match="Evidence is missing"):
        controller.approve("op-1", approval_id="a", actor="reviewer", expires_at=150)


def test_approval_id_replay_never_renews_or_rebinds_authority(controller, policy, intent):
    action = approve(controller, policy, intent)
    assert (
        controller.approve("op-1", approval_id="approval-1", actor="reviewer", expires_at=150)
        == action
    )
    with pytest.raises(LedgerConflict, match="immutable binding"):
        controller.approve("op-1", approval_id="approval-1", actor="reviewer", expires_at=151)
    controller.revoke("approval-1", actor="reviewer", reason="withdrawn")
    replayed = controller.approve(
        "op-1", approval_id="approval-1", actor="reviewer", expires_at=150
    )
    assert not replayed.authorized
    with pytest.raises(AuthorizationDenied, match="revoked"):
        admit(controller, replayed)


def test_revocation_fences_only_the_current_grant_and_is_idempotent(controller, policy, intent):
    approve(controller, policy, intent)
    current = controller.approve("op-1", approval_id="new", actor="other", expires_at=150)
    with pytest.raises(AuthorizationDenied, match="owner or administrator"):
        controller.revoke("new", actor="reviewer", reason="not mine")
    assert controller.revoke("approval-1", actor="owner", reason="superseded") == current
    active = admit(controller, current)
    revoked = controller.revoke("new", actor="owner", reason="cancel")
    assert revoked.generation > active.generation
    assert revoked.attempts[0].phase is Phase.UNSENT
    assert controller.revoke("new", actor="owner", reason="cancel") == revoked
    with pytest.raises(TransitionError, match="Stale"):
        send(controller, active)
    with pytest.raises(LedgerConflict, match="Unknown approval"):
        controller.revoke("absent", actor="owner", reason="cancel")


def test_revocation_preserves_unknown_effect_and_does_not_authorize_repetition(
    controller, policy, intent
):
    released = send(controller, admit(controller, approve(controller, policy, intent)))
    revoked = controller.revoke("approval-1", actor="reviewer", reason="withdrawn")
    assert revoked.effect is Effect.UNKNOWN
    assert revoked.attempts == released.attempts
    renewed = controller.approve("op-1", approval_id="new", actor="reviewer", expires_at=150)
    with pytest.raises(TransitionError, match="safe-repetition"):
        admit(controller, renewed, "attempt-2")


@pytest.mark.parametrize("revoke", [False, True])
def test_grant_or_revocation_and_state_roll_back_on_journal_failure(
    controller, policy, intent, revoke
):
    before = approve(controller, policy, intent) if revoke else prepare(controller, policy, intent)
    with sqlite3.connect(controller.ledger.path) as db:
        db.execute(
            "CREATE TRIGGER fail_journal BEFORE INSERT ON journal "
            "BEGIN SELECT RAISE(ABORT,'injected'); END"
        )
    with pytest.raises(sqlite3.IntegrityError, match="injected"):
        if revoke:
            controller.revoke("approval-1", actor="owner", reason="withdrawn")
        else:
            controller.approve("op-1", approval_id="a", actor="reviewer", expires_at=150)
    assert controller.ledger.get("op-1") == before
    with sqlite3.connect(controller.ledger.path) as db:
        assert db.execute("SELECT count(*) FROM approvals").fetchone()[0] == int(revoke)
        assert db.execute("SELECT count(*) FROM revocations").fetchone()[0] == 0


def downgrade_reference_fixture(path):
    with sqlite3.connect(path) as db:
        for table in (*DISPATCH_IMMUTABLE, *AUTHORITY_IMMUTABLE, "authority_config"):
            db.execute(f"DROP TABLE {table}")
        db.execute("ALTER TABLE ledger_meta DROP COLUMN mode")
        db.execute("PRAGMA user_version=1")


def test_v1_reference_migration_preserves_data_and_never_promotes_authority(tmp_path, intent):
    path = tmp_path / "legacy.sqlite"
    original = Ledger(path, organization_id="org-1")
    action = original.submit(intent, provider_key="key-1")
    history = original.history("op-1")
    downgrade_reference_fixture(path)
    with pytest.raises(LedgerFormatError, match="cannot become governed"):
        Authority(path, organization_id="org-1", administrators=frozenset({"owner"}))
    migrated = Ledger(path, organization_id="org-1")
    assert migrated.get("op-1") == action
    assert migrated.history("op-1") == history
    assert migrated.reservation("sim.resource", "event-1") == "op-1"
    with sqlite3.connect(path) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
    with pytest.raises(LedgerFormatError, match="mode"):
        Authority(path, organization_id="org-1", administrators=frozenset({"owner"}))


def test_migration_failure_rolls_back_schema_and_preserves_data(tmp_path, intent, monkeypatch):
    path = tmp_path / "legacy.sqlite"
    Ledger(path, organization_id="org-1").submit(intent, provider_key="key-1")
    downgrade_reference_fixture(path)
    with monkeypatch.context() as patch:

        def fail(*_):
            raise RuntimeError("migration failure")

        patch.setattr(Ledger, "_retain", staticmethod(fail))
        with pytest.raises(RuntimeError, match="migration failure"):
            Ledger(path, organization_id="org-1")
    with sqlite3.connect(path) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 1
        assert "mode" not in [row[1] for row in db.execute("PRAGMA table_info(ledger_meta)")]
    assert Ledger(path, organization_id="org-1").get("op-1").intent == intent


def _racing_authority(path, send_boundary, revoker, version, generation, connection):
    controller = Authority(
        path, organization_id="org-1", administrators=frozenset({"owner"}), clock=lambda: 100
    )
    connection.send("ready")
    connection.recv()
    try:
        if revoker:
            controller.revoke("approval-1", actor="owner", reason="race")
        else:
            method = controller.mark_send_possible if send_boundary else controller.admit
            method("op-1", expected_version=version, generation=generation, attempt_id="attempt-1")
        connection.send("ok")
    except TransitionError:
        connection.send("stale")


@pytest.mark.parametrize("send_boundary", [False, True])
def test_revocation_races_serialize_against_admission_and_boundary(
    controller, policy, intent, send_boundary
):
    action = approve(controller, policy, intent)
    if send_boundary:
        action = admit(controller, action)
    arguments = (controller.ledger.path, send_boundary)
    with (
        process(_racing_authority, *arguments, True, action.version, action.generation) as (
            revoker,
            pipe1,
        ),
        process(_racing_authority, *arguments, False, action.version, action.generation) as (
            worker,
            pipe2,
        ),
    ):
        assert receive(pipe1) == receive(pipe2) == "ready"
        pipe1.send("go")
        pipe2.send("go")
        assert receive(pipe1) == "ok"
        assert receive(pipe2) in ("ok", "stale")
        revoker.join(timeout=10)
        worker.join(timeout=10)
        assert revoker.exitcode == worker.exitcode == 0
    current = controller.ledger.get("op-1")
    assert not current.authorized
    assert all(attempt.phase is not Phase.ADMITTED for attempt in current.attempts)
    assert current.effect in (Effect.UNKNOWN, Effect.NOT_ATTEMPTED)
    if current.effect is Effect.UNKNOWN:
        assert send_boundary


@pytest.mark.parametrize(
    "changes",
    [
        {"adapter_digest": "invalid"},
        {"resources": set()},
        {"approvers": frozenset()},
        {"resources": frozenset(str(i) for i in range(33))},
        {"max_quantity": True},
        {"approval_ttl_seconds": 86401},
    ],
)
def test_policy_validation(policy, changes):
    with pytest.raises(ValidationError):
        replace(policy, **changes)


def test_policy_wire_and_control_inputs_are_closed(controller, policy, intent, monkeypatch):
    assert Policy.from_json(policy.canonical) == policy
    value = json.loads(policy.canonical)
    value["resources"] *= 2
    with pytest.raises(ValidationError):
        Policy.from_json(json.dumps(value).encode())
    with pytest.raises(ValidationError):
        controller.configure({}, actor="owner", expected_revision=0)
    with pytest.raises(ValidationError):
        record_evidence(controller, {}, actor="owner", expected_revision=0, expires_at=150)
    with pytest.raises(ValidationError):
        Authority(controller.ledger.path, organization_id="org-1", administrators=set())
    with pytest.raises(ValidationError):
        Ledger(controller.ledger.path, organization_id="org-1", mode="governed")
    monkeypatch.setattr("work_steward.authority.time.time_ns", lambda: 101_000_000_000)
    real_clock = Authority(
        controller.ledger.path, organization_id="org-1", administrators=frozenset({"owner"})
    )
    real_clock.configure(policy, actor="owner", expected_revision=0)
    with sqlite3.connect(controller.ledger.path) as db:
        assert db.execute("SELECT last_tick FROM authority_config").fetchone()[0] == 101


def _crashing_approval(path, before_commit, connection):
    controller = Authority(
        path, organization_id="org-1", administrators=frozenset({"owner"}), clock=lambda: 100
    )
    journal = Ledger._journal

    def barrier(db, *arguments):
        journal(db, *arguments)
        if before_commit:
            connection.send("uncommitted")
            connection.recv()

    Ledger._journal = staticmethod(barrier)
    controller.approve("op-1", approval_id="approval-1", actor="reviewer", expires_at=150)
    connection.send("committed")
    connection.recv()


@pytest.mark.parametrize("before_commit", [True, False])
def test_process_death_commits_all_or_none_of_approval_and_state(
    controller, policy, intent, before_commit
):
    before = prepare(controller, policy, intent)
    with process(_crashing_approval, controller.ledger.path, before_commit) as (worker, connection):
        assert receive(connection) == ("uncommitted" if before_commit else "committed")
        worker.kill()
        worker.join(timeout=10)
    restarted = Authority(
        controller.ledger.path,
        organization_id="org-1",
        administrators=frozenset({"owner"}),
        clock=lambda: 100,
    )
    current = restarted.ledger.get("op-1")
    assert current.authorized is (not before_commit)
    with sqlite3.connect(controller.ledger.path) as db:
        assert db.execute("SELECT count(*) FROM approvals").fetchone()[0] == int(not before_commit)
    assert len(restarted.ledger.history("op-1")) == (1 if before_commit else 2)
    if before_commit:
        assert current == before
    else:
        assert admit(restarted, current).attempts[0].phase is Phase.ADMITTED


def test_clock_configuration_and_values_fail_closed(controller, policy):
    with pytest.raises(ValidationError, match="Clock"):
        Authority(
            controller.ledger.path,
            organization_id="org-1",
            administrators=frozenset({"owner"}),
            clock=100,
        )
    controller._clock.value = True
    with pytest.raises(ValidationError, match="clock"):
        controller.configure(policy, actor="owner", expected_revision=0)


def test_closed_operation_cannot_receive_new_approval(controller, policy, intent):
    prepare(controller, policy, intent)
    with controller.ledger._transaction(write=True) as db:
        before = controller.ledger._load(db, "op-1")
        after = before.stop(close=True)
        controller._save(db, before, after, "fixture_close", {})
    with pytest.raises(AuthorizationDenied, match="Closed"):
        controller.approve("op-1", approval_id="a", actor="reviewer", expires_at=150)
