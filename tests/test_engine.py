import json
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import replace
from http.client import RemoteDisconnected
from itertools import pairwise
from uuid import uuid4

import pytest
from conftest import process, receive
from hypothesis import HealthCheck, example, given, note, settings
from hypothesis import strategies as st

from work_steward.authority import Authority, AuthorizationDenied, Policy
from work_steward.canonical import ValidationError
from work_steward.engine import Engine
from work_steward.intent import Consistency
from work_steward.ledger import LedgerConflict
from work_steward.ledger_schema import DISPATCH_IMMUTABLE, SCHEMA_VERSION
from work_steward.model import Effect, Phase, TransitionError
from work_steward.synthetic import ADAPTER_DIGEST, ADAPTER_ID, SUPPORTED_CONSISTENCY
from work_steward.transport import Endpoint, Reply


@pytest.fixture
def engine_provider(tmp_path, provider, intent):
    @contextmanager
    def start(*, profile="permanent", behavior="apply", prepared=True, approved=True, clock=None):
        with provider(
            database=tmp_path / (uuid4().hex + ".provider.sqlite"),
            profile=profile,
            behavior=behavior,
        ) as destination:
            authority = Authority(
                tmp_path / (uuid4().hex + ".sqlite"),
                organization_id="org-1",
                administrators=frozenset({"owner"}),
                clock=clock if clock is not None else lambda: 100,
            )
            engine = Engine(authority, endpoint=Endpoint(destination.port), account=intent.account)
            proposal = replace(intent, adapter_id=ADAPTER_ID, adapter_digest=ADAPTER_DIGEST)
            authority.configure(
                Policy(
                    proposal.account,
                    proposal.capability,
                    ADAPTER_ID,
                    ADAPTER_DIGEST,
                    frozenset({proposal.resource}),
                    frozenset({"owner"}),
                    10,
                ),
                actor="owner",
                expected_revision=0,
            )
            authority.permit_read(
                "read-1",
                actor="owner",
                account=proposal.account,
                capability=proposal.capability,
                resources=frozenset({proposal.resource}),
                expires_at=200,
                administrator="owner",
            )
            engine.ledger.submit(
                proposal,
                provider_key="key-1",
                idempotency=engine.profile.idempotency,
                supported_consistency=SUPPORTED_CONSISTENCY,
            )
            if prepared:
                engine.prepare("op-1")
            if approved:
                authority.approve("op-1", approval_id="approval-1", actor="owner", expires_at=150)
            yield engine, destination, proposal

    return start


def test_exact_request_and_confirmation_are_durable(engine_provider):
    with engine_provider() as (engine, destination, intent):
        first = engine.dispatch("op-1", actor="owner")
        assert first.effect is Effect.CONFIRMED
        assert engine.dispatch("op-1", actor="owner") == first
        assert destination.oracle() == (1, 1)
        reopened = Engine(engine.authority)
        detail = reopened.inspect("op-1")
        assert detail["effect"] == "effect_confirmed"
        assert detail["history"][-1]["version"] == first.version
        assert detail["responses"][0]["admitted"] == 1
        assert detail["approvals"][0]["request_digest"] == detail["prepared_request"]["digest"]
        assert (
            json.loads(detail["prepared_request"]["request"]["body"])["account"] == intent.account
        )


def test_preparation_after_approval_requires_fresh_bound_approval(engine_provider):
    with engine_provider(prepared=False) as (engine, destination, _):
        prepared = engine.prepare("op-1")
        assert engine.prepare("op-1") == prepared
        with pytest.raises(AuthorizationDenied, match="prepared"):
            engine.dispatch("op-1", actor="owner")
        with pytest.raises(LedgerConflict):
            engine.authority.approve(
                "op-1", approval_id="approval-1", actor="owner", expires_at=150
            )
        assert destination.oracle() == (0, 0)
        engine.authority.approve("op-1", approval_id="new", actor="owner", expires_at=150)
        assert engine.dispatch("op-1", actor="owner").effect is Effect.CONFIRMED


@pytest.mark.parametrize("change", ["policy", "revocation", "cancellation"])
def test_current_authority_is_checked_again_before_transport(engine_provider, monkeypatch, change):
    with engine_provider() as (engine, destination, _):
        release = engine._release

        def race(action, request):
            if change == "policy":
                revision, policy = engine.authority.current_policy()
                engine.authority.configure(policy, actor="owner", expected_revision=revision)
            elif change == "revocation":
                engine.authority.revoke("approval-1", actor="owner", reason="race")
            else:
                engine.cancel("op-1", actor="owner")
            return release(action, request)

        monkeypatch.setattr(engine, "_release", race)
        with pytest.raises((AuthorizationDenied, TransitionError)):
            engine.dispatch("op-1", actor="owner")
        assert destination.oracle() == (0, 0)
        assert all(a.phase is not Phase.POSSIBLY_SENT for a in engine.ledger.get("op-1").attempts)


@pytest.mark.parametrize(
    "behavior",
    ["drop_after_apply", "pending", "reject", "duplicate_status", "contradictory_status"],
)
def test_verified_response_and_reconciliation_profiles(engine_provider, behavior):
    with engine_provider(behavior=behavior) as (engine, destination, _):
        result = engine.dispatch("op-1", actor="owner")
        expected = {
            "drop_after_apply": Effect.UNKNOWN,
            "pending": Effect.PENDING,
            "reject": Effect.NO_EFFECT,
        }.get(behavior, Effect.CONFIRMED)
        assert result.effect is expected
        observed = engine.reconcile("op-1", actor="owner")
        expected = {
            "drop_after_apply": Effect.CONFIRMED,
            "contradictory_status": Effect.CONFLICTING,
        }.get(behavior, expected)
        assert observed.effect is expected
        assert destination.oracle()[0] == int(behavior not in {"pending", "reject"})


def test_read_permission_is_current_and_independent_of_write_revocation(engine_provider):
    with engine_provider(behavior="drop_after_apply") as (engine, _, _):
        engine.dispatch("op-1", actor="owner")
        engine.authority.revoke("approval-1", actor="owner", reason="stop new effects")
        engine.cancel("op-1", actor="owner")
        assert engine.reconcile("op-1", actor="owner").effect is Effect.CONFIRMED
        engine.authority.revoke_read("read-1", actor="owner", reason="stop reads")
        with pytest.raises(AuthorizationDenied, match="reconciliation"):
            engine.reconcile("op-1", actor="owner")
        with pytest.raises(AuthorizationDenied):
            engine.inventory("resource-1", actor="owner")


def test_late_receipt_cannot_assert_its_own_read_authority(engine_provider, monkeypatch):
    with engine_provider() as (engine, destination, _):
        transmit = engine._transmit

        def revoke_after_send(request):
            reply = transmit(request)
            engine.authority.revoke_read("read-1", actor="owner", reason="race")
            return reply

        monkeypatch.setattr(engine, "_transmit", revoke_after_send)
        assert engine.dispatch("op-1", actor="owner").effect is Effect.UNKNOWN
        assert destination.oracle() == (1, 1)
        detail = engine.inspect("op-1")
        assert detail["observations"] == []
        assert detail["responses"][0]["error"] == "read_permission_denied"
        engine.authority.permit_read(
            "restored",
            actor="owner",
            account="account-1",
            capability="sim.effect.create",
            resources=frozenset({"resource-1"}),
            expires_at=200,
            administrator="owner",
        )
        assert engine.reconcile("op-1", actor="owner").effect is Effect.CONFIRMED


@pytest.mark.parametrize(
    "reply",
    [
        Reply(None, b"", error="transport_unavailable"),
        Reply(200, b'{"verified":true}', "0" * 32),
        Reply(302, b"{}"),
    ],
)
def test_unverified_response_never_establishes_no_effect(engine_provider, monkeypatch, reply):
    with engine_provider() as (engine, destination, _):
        monkeypatch.setattr(engine, "_transmit", lambda _: reply)
        result = engine.dispatch("op-1", actor="owner")
        assert result.effect is Effect.UNKNOWN
        assert destination.oracle() == (0, 0)
        assert engine.inspect("op-1")["responses"][0]["admitted"] == 0


@pytest.mark.parametrize(
    "reply",
    [
        Reply(200, b"{}", "b" * 32),
        Reply(None, b"", error="transport_unavailable"),
        Reply(200, b"partial", error="invalid_response_size"),
    ],
)
def test_rejected_response_retains_identity_and_transport_error(
    engine_provider, monkeypatch, reply
):
    with engine_provider() as (engine, destination, _):
        monkeypatch.setattr(engine, "_transmit", lambda _: reply)
        result = engine.dispatch("op-1", actor="owner")
        assert result.effect is Effect.UNKNOWN
        response = Engine(engine.authority).inspect("op-1")["responses"][0]
        assert response["provider_id"] == reply.provider_id
        assert response["transport_error"] == reply.error
        assert response["status"] == reply.status
        assert response["body"] == reply.body.decode()
        assert response["error"] == "unverified_response"
        assert response["admitted"] == 0
        assert destination.oracle() == (0, 0)


def test_admission_sql_failure_cannot_transmit_or_leave_half_an_attempt(engine_provider):
    with engine_provider() as (engine, destination, _):
        before = engine.ledger.get("op-1")
        with sqlite3.connect(engine.ledger.path) as db:
            db.execute(
                "CREATE TRIGGER reject_dispatch BEFORE INSERT ON dispatch_requests "
                "BEGIN SELECT RAISE(ABORT,'injected'); END"
            )
        with pytest.raises(sqlite3.IntegrityError, match="injected"):
            engine.dispatch("op-1", actor="owner")
        assert engine.ledger.get("op-1") == before
        assert destination.oracle() == (0, 0)


@pytest.mark.parametrize("profile", ["none", "finite"])
def test_unkeyed_and_finite_receipts_are_bound_without_permanent_coverage(engine_provider, profile):
    with engine_provider(profile=profile) as (engine, destination, _):
        assert engine.dispatch("op-1", actor="owner").effect is Effect.CONFIRMED
        assert engine.reconcile("op-1", actor="owner").effect is Effect.CONFIRMED
        assert destination.oracle() == (1, 1)
    with engine_provider(profile=profile, behavior="pending") as (engine, destination, _):
        assert engine.dispatch("op-1", actor="owner").effect is Effect.PENDING
        with pytest.raises(TransitionError, match="permanent-key"):
            engine.dispatch("op-1", actor="owner", repeat=True)
        assert len(engine.ledger.get("op-1").attempts) == 1
        assert destination.oracle() == (0, 0)


def test_destination_condition_is_atomic_even_after_a_successful_local_check(engine_provider):
    with engine_provider(prepared=False, approved=False) as (engine, destination, intent):
        changed = replace(
            intent,
            operation_id="conditional",
            business_effect_key="conditional",
            consistency=Consistency.C2,
            resource_version=0,
        )
        engine.ledger.submit(
            changed,
            provider_key="conditional",
            idempotency=engine.profile.idempotency,
            supported_consistency=SUPPORTED_CONSISTENCY,
        )
        engine.prepare("conditional")
        engine.authority.approve(
            "conditional", approval_id="conditional", actor="owner", expires_at=150
        )
        assert destination.submit(operation_id="another", key="another", quantity=1)[0] == 200
        result = engine.dispatch("conditional", actor="owner")
        assert result.effect is Effect.NO_EFFECT
        assert destination.oracle() == (1, 1)


def test_initial_binding_and_closed_or_unprepared_operations_fail_closed(tmp_path, engine_provider):
    authority = Authority(
        tmp_path / "empty.sqlite", organization_id="org-1", administrators=frozenset({"owner"})
    )
    with pytest.raises(ValidationError, match="Initial connector"):
        Engine(authority)
    with engine_provider(prepared=False, approved=True) as (engine, destination, _):
        with pytest.raises(TransitionError, match="Prepare"):
            engine.dispatch("op-1", actor="owner")
        engine.cancel("op-1", actor="owner")
        with pytest.raises(TransitionError, match="Closed"):
            engine.prepare("op-1")
        assert destination.oracle() == (0, 0)
    with engine_provider() as (engine, destination, intent):
        with pytest.raises(LedgerConflict, match="replace"):
            Engine(engine.authority, endpoint=Endpoint(1))
        with pytest.raises(LedgerConflict):
            Engine(engine.authority, account="another")
        with pytest.raises(ValidationError):
            engine.dispatch("op-1", actor="owner", repeat="true")
        other = replace(intent, operation_id="other", business_effect_key="other", account="other")
        engine.ledger.submit(other, provider_key="other", idempotency=engine.profile.idempotency)
        with pytest.raises(ValidationError, match="account"):
            engine.prepare("other")


@pytest.mark.parametrize("same_endpoint", [True, False])
def test_concurrent_connector_initialization_cannot_silently_choose_another_destination(
    tmp_path, provider, monkeypatch, same_endpoint
):
    from work_steward import transport

    authority = Authority(
        tmp_path / "engine.sqlite", organization_id="org-1", administrators=frozenset({"owner"})
    )
    barrier = threading.Barrier(2)
    read = transport.read

    def synchronized(*arguments, **kwargs):
        reply = read(*arguments, **kwargs)
        barrier.wait(timeout=5)
        return reply

    with (
        provider(database=tmp_path / "one.sqlite") as one,
        provider(database=tmp_path / "two.sqlite") as two,
    ):
        monkeypatch.setattr(transport, "read", synchronized)

        def initialize(port):
            try:
                Engine(authority, endpoint=Endpoint(port), account="account-1")
                return "bound"
            except LedgerConflict:
                return "conflict"

        with ThreadPoolExecutor(max_workers=2) as pool:
            ports = [one.port, one.port if same_endpoint else two.port]
            assert sorted(pool.map(initialize, ports)) == (
                ["bound", "bound"] if same_endpoint else ["bound", "conflict"]
            )


def test_connector_artifact_and_exact_prepared_bytes_cannot_drift(engine_provider, monkeypatch):
    from work_steward import synthetic

    with engine_provider() as (engine, destination, _):
        build = synthetic.build

        def reorder(*arguments):
            request = build(*arguments)
            return replace(request, headers=tuple(reversed(request.headers)))

        with monkeypatch.context() as patch:
            patch.setattr(synthetic, "build", reorder)
            with pytest.raises(LedgerConflict, match="cannot be replaced"):
                engine.prepare("op-1")
        monkeypatch.setattr(synthetic, "ADAPTER_DIGEST", "b" * 64)
        with pytest.raises(LedgerConflict, match="artifact"):
            engine.dispatch("op-1", actor="owner")
        assert destination.oracle() == (0, 0)


@pytest.mark.parametrize("table", ["prepared_requests", "dispatch_requests"])
def test_corrupt_stored_request_digests_never_authorize_transport(
    engine_provider, monkeypatch, table
):
    with engine_provider() as (engine, destination, _):
        if table == "dispatch_requests":
            monkeypatch.setattr(engine, "_transmit", lambda _: Reply(None, b"", error="lost"))
            engine.dispatch("op-1", actor="owner")
        with sqlite3.connect(engine.ledger.path) as db:
            db.execute(f"DROP TRIGGER retain_{table}_UPDATE")
            db.execute(f"UPDATE {table} SET digest='corrupt'")  # noqa: S608 -- fixed test table names
        with pytest.raises(ValidationError, match="digest mismatch"):
            engine.dispatch("op-1", actor="owner", repeat=table == "dispatch_requests")
        assert destination.oracle() == (0, 0)


def test_model_only_boundary_cannot_become_a_dispatch_or_repetition_capability(engine_provider):
    with engine_provider() as (engine, destination, _):
        before = engine.ledger.get("op-1")
        admitted = engine.authority.admit(
            "op-1",
            expected_version=before.version,
            generation=before.generation,
            attempt_id="model-only",
        )
        engine.authority.mark_send_possible(
            "op-1",
            expected_version=admitted.version,
            generation=admitted.generation,
            attempt_id="model-only",
        )
        assert engine.reconcile("op-1", actor="owner").effect is Effect.UNKNOWN
        with pytest.raises(ValidationError, match="Unbound previous"):
            engine.dispatch("op-1", actor="owner", repeat=True)
        assert destination.oracle() == (0, 0)


def test_release_checks_its_own_committed_request(engine_provider, monkeypatch):
    with engine_provider() as (engine, destination, _):
        release = engine._release

        def corrupt(action, request):
            with sqlite3.connect(engine.ledger.path) as db:
                db.execute("DROP TRIGGER retain_dispatch_requests_UPDATE")
                db.execute("UPDATE dispatch_requests SET digest='corrupt'")
            return release(action, request)

        monkeypatch.setattr(engine, "_release", corrupt)
        with pytest.raises(AuthorizationDenied, match="binding"):
            engine.dispatch("op-1", actor="owner")
        assert destination.oracle() == (0, 0)


def test_read_grants_are_scoped_bounded_immutable_and_revocable(engine_provider):
    with engine_provider() as (engine, _, intent):
        authority = engine.authority
        arguments = {
            "actor": "owner",
            "account": intent.account,
            "capability": intent.capability,
            "resources": frozenset({intent.resource}),
            "expires_at": 200,
            "administrator": "owner",
        }
        authority.permit_read("read-1", **arguments)
        with pytest.raises(LedgerConflict, match="another binding"):
            authority.permit_read("read-1", **{**arguments, "expires_at": 201})
        with pytest.raises(ValidationError, match="bounded set"):
            authority.permit_read("read-2", **{**arguments, "resources": frozenset()})
        with pytest.raises(AuthorizationDenied, match="expiry"):
            authority.permit_read("read-2", **{**arguments, "expires_at": 100})
        with pytest.raises(LedgerConflict, match="Unknown read"):
            authority.revoke_read("missing", actor="owner", reason="withdraw")
        authority.revoke_read("read-1", actor="owner", reason="withdraw")
        authority.revoke_read("read-1", actor="owner", reason="withdraw")
        authority.permit_read("read-1", **arguments)
        with pytest.raises(AuthorizationDenied):
            engine.inventory(intent.resource, actor="owner")


def _released_sender(path, pipe):
    _paused_sender(path, False, pipe)


def _paused_sender(path, transmit_before_pause, pipe):
    authority = Authority(
        path, organization_id="org-1", administrators=frozenset({"owner"}), clock=lambda: 100
    )
    engine = Engine(authority)
    transmit = engine._transmit

    def paused(request):
        reply = transmit(request) if transmit_before_pause else None
        pipe.send("released")
        pipe.recv()
        return reply if transmit_before_pause else transmit(request)

    engine._transmit = paused
    engine.dispatch("op-1", actor="owner")
    pipe.send("observed")


def test_permanent_retry_and_resumed_sender_deduplicate_without_a_version_condition(
    engine_provider,
):
    with (
        engine_provider() as (engine, destination, intent),
        process(_released_sender, engine.ledger.path) as (worker, pipe),
    ):
        assert intent.consistency is Consistency.C0 and intent.resource_version is None
        assert receive(pipe) == "released"
        engine.recover("op-1", actor="owner")
        assert engine.reconcile("op-1", actor="owner").effect is Effect.UNKNOWN
        assert destination.oracle() == (0, 0)
        repeated = engine.dispatch("op-1", actor="owner", repeat=True)
        assert repeated.effect is Effect.CONFIRMED
        assert repeated.attempts[-1].repetition_covered == frozenset(
            {repeated.attempts[0].attempt_id}
        )
        pipe.send("resume")
        assert receive(pipe) == "observed"
        worker.join(timeout=5)
        assert worker.exitcode == 0
        after = engine.ledger.get("op-1")
        assert after.effect is Effect.CONFIRMED and len(after.attempts) == 2
        assert all(a.assessment is Effect.CONFIRMED for a in after.attempts)
        assert destination.oracle() == (1, 1)


@pytest.mark.parametrize("transmit_before_pause", [False, True])
def test_provider_restart_and_resumed_sender_preserve_permanent_key(
    engine_provider, provider, transmit_before_pause
):
    with (
        engine_provider() as (engine, destination, intent),
        process(_paused_sender, engine.ledger.path, transmit_before_pause) as (worker, pipe),
    ):
        assert intent.consistency is Consistency.C0 and intent.resource_version is None
        assert receive(pipe) == "released"
        before = engine.ledger.get("op-1")
        assert before.effect is Effect.UNKNOWN
        assert before.attempts[0].phase is Phase.POSSIBLY_SENT
        assert destination.oracle() == (int(transmit_before_pause), int(transmit_before_pause))
        binding = Engine.configuration(engine.authority)
        destination.process.kill()
        destination.process.wait(timeout=5)
        with provider(database=destination.database, port=destination.port) as restarted:
            assert restarted.request("GET", "/v1/profile") == (200, engine.profile.value)
            engine = Engine(engine.authority)
            assert engine.endpoint == Endpoint(restarted.port)
            assert Engine.configuration(engine.authority) == binding
            engine.recover("op-1", actor="owner")
            if not transmit_before_pause:
                assert engine.reconcile("op-1", actor="owner").effect is Effect.UNKNOWN
            repeated = engine.dispatch("op-1", actor="owner", repeat=True)
            assert repeated.effect is Effect.CONFIRMED
            assert repeated.attempts[-1].repetition_covered == frozenset(
                {before.attempts[0].attempt_id}
            )
            pipe.send("resume")
            assert receive(pipe) == "observed"
            worker.join(timeout=5)
            assert worker.exitcode == 0
            after = Engine(engine.authority).inspect("op-1")
            attempts = {attempt["attempt_id"] for attempt in after["attempts"]}
            assert after["effect"] == "effect_confirmed" and len(attempts) == 2
            assert {fact["attempt_id"] for fact in after["observations"]} == attempts
            record = restarted.lookup()[1]["records"][0]
            assert (
                record["attempt_id"]
                == repeated.attempts[0 if transmit_before_pause else 1].attempt_id
            )
            assert {fact["provider_effect_id"] for fact in after["observations"]} == {
                record["provider_effect_id"]
            }
            assert all(response["admitted"] for response in after["responses"])
            assert restarted.oracle() == (1, 1)


@settings(
    max_examples=20,
    deadline=None,
    derandomize=True,
    database=None,
    print_blob=True,
    # Each example opens a fresh provider process and UUID-named databases.
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@example(
    commands=[("dispatch", 0), ("recover", 0), ("dispatch", 0), ("retry", 0), ("reconcile", 0)]
)
@example(commands=[("retry", 0)] * 4 + [("reconcile", 0), ("dispatch", 100)])
@example(commands=[("reconcile", 0), ("dispatch", 0), ("retry", 50), ("reconcile", 0)])
@example(commands=[("dispatch", 0), ("reconcile", 100), ("recover", 0), ("retry", 0)])
@given(
    commands=st.lists(
        st.tuples(
            st.sampled_from(["dispatch", "retry", "reconcile", "recover"]),
            st.sampled_from([0, 1, 50, 100]),
        ),
        min_size=1,
        max_size=10,
    )
)
def test_generated_permanent_key_recovery_schedules(engine_provider, commands):
    now = 100
    with engine_provider(behavior="drop_after_apply", clock=lambda: now) as (
        engine,
        destination,
        intent,
    ):
        assert intent.consistency is Consistency.C0 and intent.resource_version is None
        sent, confirmed = 0, False
        wire = []
        prepared = engine.inspect("op-1")["prepared_request"]
        history = engine.ledger.history("op-1")
        for index, (command, advance) in enumerate(commands):
            now += advance
            note(f"Executed prefix: {commands[: index + 1]!r}; clock={now}")
            authority = Authority(
                engine.ledger.path,
                organization_id="org-1",
                administrators=frozenset({"owner"}),
                clock=lambda tick=now: tick,
            )
            engine = Engine(authority)

            def transmit(request):
                wire.append(request)
                return Engine._transmit(request)

            engine._transmit = transmit
            failure = None
            if command in {"dispatch", "retry"} and not confirmed:
                if now >= 150:
                    failure = AuthorizationDenied
                elif sent >= 3 or (sent and command == "dispatch"):
                    failure = TransitionError
            elif command == "reconcile":
                failure = (
                    AuthorizationDenied if now >= 200 else TransitionError if not sent else None
                )

            def execute(engine=engine, command=command):
                if command in {"dispatch", "retry"}:
                    return engine.dispatch("op-1", actor="owner", repeat=command == "retry")
                if command == "reconcile":
                    return engine.reconcile("op-1", actor="owner")
                return engine.recover("op-1", actor="owner")

            if failure is not None:
                with pytest.raises(failure):
                    execute()
            else:
                execute()
                if command in {"dispatch", "retry"} and not confirmed:
                    sent += 1
                elif command == "reconcile":
                    confirmed = True

            assert len(wire) == sent
            assert destination.oracle() == (int(sent > 0), int(sent > 0))
            reopened = Engine(authority)
            action = reopened.ledger.get("op-1")
            assert len(action.attempts) == sent
            assert action.effect is (
                Effect.CONFIRMED if confirmed else Effect.UNKNOWN if sent else Effect.NOT_ATTEMPTED
            )
            assert all(attempt.phase is Phase.POSSIBLY_SENT for attempt in action.attempts)
            for ordinal, attempt in enumerate(action.attempts):
                assert attempt.repetition_covered == frozenset(
                    previous.attempt_id for previous in action.attempts[:ordinal]
                )
            detail = reopened.inspect("op-1")
            assert detail["prepared_request"] == prepared
            persisted = reopened.ledger.history("op-1")
            assert persisted[: len(history)] == history
            assert all(
                current.previous_version == previous.version and current.version > previous.version
                for previous, current in pairwise(persisted)
            )
            last = persisted[-1]
            assert (last.version, last.generation, last.effect, last.disposition) == (
                action.version,
                action.generation,
                action.effect,
                action.disposition,
            )
            assert sum(entry.command == "send_possible" for entry in persisted) == sent
            assert {dict(request.headers)["X-WS-Attempt-ID"] for request in wire} == {
                attempt.attempt_id for attempt in action.attempts
            }
            history = persisted


def test_permanent_retry_after_an_applied_lost_response_has_one_unconditional_effect(
    engine_provider,
):
    with engine_provider(behavior="drop_after_apply") as (engine, destination, intent):
        assert intent.resource_version is None
        assert engine.dispatch("op-1", actor="owner").effect is Effect.UNKNOWN
        assert engine.dispatch("op-1", actor="owner", repeat=True).effect is Effect.UNKNOWN
        after = engine.reconcile("op-1", actor="owner")
        assert after.effect is Effect.CONFIRMED and len(after.attempts) == 2
        assert all(a.assessment is Effect.CONFIRMED for a in after.attempts)
        assert destination.oracle() == (1, 1)


def test_unkeyed_retry_guard_prevents_a_real_unconditional_duplicate(engine_provider):
    with engine_provider(profile="none", behavior="drop_after_apply") as (
        engine,
        destination,
        intent,
    ):
        assert intent.consistency is Consistency.C0 and intent.resource_version is None
        assert engine.dispatch("op-1", actor="owner").effect is Effect.UNKNOWN
        with pytest.raises(TransitionError, match="permanent-key"):
            engine.dispatch("op-1", actor="owner", repeat=True)
        assert destination.oracle() == (1, 1)
        assert len(engine.ledger.get("op-1").attempts) == 1
        # Harness-only counterexample: bypassing the engine really duplicates this write.
        with pytest.raises(RemoteDisconnected):
            destination.submit(key=None, attempt="blind-retry")
        assert destination.oracle() == (2, 2)


def test_released_old_sender_can_finish_after_revocation_without_reopening_authority(
    engine_provider,
):
    with (
        engine_provider() as (engine, destination, _),
        process(_released_sender, engine.ledger.path) as (worker, pipe),
    ):
        assert receive(pipe) == "released"
        engine.authority.revoke("approval-1", actor="owner", reason="too late to recall")
        cancelled = engine.cancel("op-1", actor="owner")
        assert cancelled.effect is Effect.UNKNOWN
        assert engine.reconcile("op-1", actor="owner").effect is Effect.UNKNOWN
        assert destination.oracle() == (0, 0)
        pipe.send("resume")
        assert receive(pipe) == "observed"
        worker.join(timeout=5)
        assert worker.exitcode == 0
        after = engine.ledger.get("op-1")
        assert after.effect is Effect.CONFIRMED and not after.authorized
        assert after.disposition.value == "closed"
        assert destination.oracle() == (1, 1)


def test_read_revocation_during_inventory_lookup_blocks_evidence_delivery(
    engine_provider, monkeypatch
):
    from work_steward import transport

    with engine_provider() as (engine, _, _):
        read = transport.read

        def withdraw(endpoint, path, provider_id=None):
            result = read(endpoint, path, provider_id)
            if path.startswith("/v1/resources"):
                engine.authority.revoke_read("read-1", actor="owner", reason="read race")
            return result

        monkeypatch.setattr(transport, "read", withdraw)
        with pytest.raises(AuthorizationDenied):
            engine.inventory("resource-1", actor="owner")


def test_v2_governed_migration_retains_approvals_without_granting_transport(engine_provider):
    with engine_provider(prepared=False) as (engine, destination, intent):
        before = engine.ledger.get("op-1")
        with sqlite3.connect(engine.ledger.path) as db:
            for table in DISPATCH_IMMUTABLE:
                db.execute(f"DROP TABLE {table}")
            db.execute("ALTER TABLE approvals DROP COLUMN request_digest")
            db.execute("PRAGMA user_version=2")
        authority = Authority(
            engine.ledger.path,
            organization_id="org-1",
            administrators=frozenset({"owner"}),
            clock=lambda: 100,
        )
        assert authority.ledger.get("op-1") == before
        upgraded = Engine(authority, endpoint=Endpoint(destination.port), account=intent.account)
        assert upgraded.inspect("op-1")["approvals"][0]["request_digest"] is None
        upgraded.prepare("op-1")
        with pytest.raises(AuthorizationDenied, match="bind"):
            upgraded.dispatch("op-1", actor="owner")
        assert destination.oracle() == (0, 0)
        with sqlite3.connect(engine.ledger.path) as db:
            assert db.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION


def test_nonterminal_polls_do_not_exhaust_a_safely_admitted_retry(engine_provider, monkeypatch):
    with engine_provider(behavior="pending") as (engine, destination, _):
        assert engine.dispatch("op-1", actor="owner").effect is Effect.PENDING
        release = engine._release

        def poll_between_admission_and_boundary(action, request):
            for _ in range(6):
                engine.reconcile("op-1", actor="owner")
                assert engine.ledger.get("op-1").attempts[-1].phase is Phase.ADMITTED
            return release(action, request)

        monkeypatch.setattr(engine, "_release", poll_between_admission_and_boundary)
        after = engine.dispatch("op-1", actor="owner", repeat=True)
        assert after.effect is Effect.PENDING and len(after.attempts) == 2
        assert destination.oracle() == (0, 0)


@pytest.mark.parametrize("boundary", ["send_possible", "provider_response"])
def test_storage_failure_at_send_or_receipt_boundary_preserves_recovery(engine_provider, boundary):
    with engine_provider() as (engine, destination, _):
        with sqlite3.connect(engine.ledger.path) as db:
            db.execute(
                "CREATE TRIGGER injected_failure BEFORE INSERT ON journal "
                f"WHEN NEW.command='{boundary}' BEGIN SELECT RAISE(ABORT,'injected'); END"
            )
        with pytest.raises(sqlite3.IntegrityError, match="injected"):
            engine.dispatch("op-1", actor="owner")
        current = engine.ledger.get("op-1")
        assert current.effect is (
            Effect.NOT_ATTEMPTED if boundary == "send_possible" else Effect.UNKNOWN
        )
        assert destination.oracle()[0] == int(boundary == "provider_response")
        with sqlite3.connect(engine.ledger.path) as db:
            assert db.execute("SELECT count(*) FROM provider_responses").fetchone()[0] == 0
            db.execute("DROP TRIGGER injected_failure")
        engine.recover("op-1", actor="owner")
        after = (
            engine.dispatch("op-1", actor="owner")
            if boundary == "send_possible"
            else engine.reconcile("op-1", actor="owner")
        )
        assert after.effect is Effect.CONFIRMED
        assert destination.oracle() == (1, 1)


def test_expired_deduplication_window_never_proves_repetition_safe(engine_provider):
    from work_steward.model import Idempotency
    from work_steward.simulator.store import Behavior, ProviderStore

    with engine_provider(profile="finite", behavior="drop_after_apply") as (engine, destination, _):
        assert engine.dispatch("op-1", actor="owner").effect is Effect.UNKNOWN
        harness = ProviderStore(
            destination.database, idempotency=Idempotency.FINITE, behavior=Behavior.DROP_AFTER_APPLY
        )
        harness.advance_clock(100)
        with pytest.raises(TransitionError, match="permanent-key"):
            engine.dispatch("op-1", actor="owner", repeat=True)
        assert destination.oracle() == (1, 1)
        assert engine.reconcile("op-1", actor="owner").effect is Effect.CONFIRMED


def test_reconciliation_expiry_is_separate_from_expired_send_permission(engine_provider):
    with engine_provider(behavior="drop_after_apply") as (engine, destination, intent):
        engine.dispatch("op-1", actor="owner")
        engine.authority._clock = lambda: 200
        with pytest.raises(AuthorizationDenied, match="reconciliation"):
            engine.reconcile("op-1", actor="owner")
        engine.authority.permit_read(
            "fresh-read",
            actor="owner",
            account=intent.account,
            capability=intent.capability,
            resources=frozenset({intent.resource}),
            expires_at=300,
            administrator="owner",
        )
        assert engine.reconcile("op-1", actor="owner").effect is Effect.CONFIRMED
        assert destination.oracle() == (1, 1)
