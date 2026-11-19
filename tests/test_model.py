from dataclasses import replace
from itertools import product

import pytest
from hypothesis import settings
from hypothesis import strategies as st
from hypothesis.stateful import RuleBasedStateMachine, initialize, invariant, rule

from work_steward.canonical import ValidationError
from work_steward.intent import Consistency, Intent
from work_steward.model import (
    Action,
    Attempt,
    Idempotency,
    Observation,
    Phase,
    RepetitionProof,
    TransitionError,
    legal_dimensions,
)
from work_steward.model import (
    Disposition as D,
)
from work_steward.model import (
    Effect as E,
)
from work_steward.model import (
    Reconciliation as R,
)


def admitted(action, attempt="a1", proof=None):
    return action.admit(
        attempt, expected_version=action.version, generation=action.generation, proof=proof
    )


def sent(action, attempt="a1"):
    return action.cross_send_boundary(
        attempt, expected_version=action.version, generation=action.generation
    )


def claim(action, effect, *, attempt="a1", observation="o1", effect_id="effect-1"):
    return Observation(
        observation,
        attempt,
        action.intent.intent_digest,
        effect,
        effect_id if effect is E.CONFIRMED else None,
    )


def observe(action, effect, **kwargs):
    return action.observe(claim(action, effect, **kwargs), expected_version=action.version)


def proof(action, **changes):
    values = {
        "intent_digest": action.intent.intent_digest,
        "covered_attempt_ids": frozenset(
            a.attempt_id for a in action.attempts if a.phase is Phase.POSSIBLY_SENT
        ),
        "account": action.intent.account,
        "capability": action.intent.capability,
        "provider_key": action.provider_key,
    }
    return RepetitionProof(**(values | changes))


def test_exhaustive_dimension_relation_matches_reviewed_table():
    expected = set()

    def rows(ds, es, rs):
        expected.update(product(ds, es, rs))

    rows([D.PROPOSED], [E.NOT_ATTEMPTED], [R.IDLE])
    rows([D.BLOCKED, D.ELIGIBLE], [E.NOT_ATTEMPTED, E.NO_EFFECT], [R.IDLE])
    rows([D.ADMITTED], [E.NOT_ATTEMPTED, E.NO_EFFECT, E.UNKNOWN], [R.IDLE])
    rows([D.PAUSED], [E.NOT_ATTEMPTED, E.NO_EFFECT], [R.IDLE, R.HUMAN])
    rows([D.PAUSED, D.CLOSED], [E.UNKNOWN, E.PENDING], [R.SCHEDULED, R.INVESTIGATING, R.HUMAN])
    rows([D.PAUSED, D.CLOSED], [E.CONFLICTING], [R.HUMAN])
    rows([D.CLOSED], [E.NOT_ATTEMPTED, E.NO_EFFECT], [R.IDLE])
    rows([D.CLOSED], [E.CONFIRMED], list(R))
    for d, e, r in product(D, E, R):
        assert legal_dimensions(d, e, r) == ((d, e, r) in expected)
    assert not legal_dimensions("closed", E.CONFIRMED, R.IDLE)


def test_recovery_before_send_fences_old_worker_but_allows_fresh_attempt(intent):
    original = admitted(Action(intent, "key-1").evaluate())
    recovered = original.takeover()
    assert recovered.effect is E.NOT_ATTEMPTED
    assert recovered.attempts[0].phase is Phase.UNSENT
    with pytest.raises(TransitionError):
        sent(recovered)
    fresh = admitted(recovered, "a2")
    assert sent(fresh, "a2").effect is E.UNKNOWN
    assert original.attempts[0].phase is Phase.ADMITTED  # immutable old snapshot


def test_boundary_is_single_use_and_timeout_is_unknown(intent):
    action = sent(admitted(Action(intent, "key").evaluate()))
    with pytest.raises(TransitionError):
        sent(action)
    stopped = action.takeover()
    assert stopped.effect is E.UNKNOWN
    assert stopped.reconciliation is R.SCHEDULED
    with pytest.raises(TransitionError):
        admitted(stopped, "a2")
    assert observe(stopped, E.UNKNOWN).effect is E.UNKNOWN


@pytest.mark.parametrize("kind", [Idempotency.NONE, Idempotency.FINITE])
def test_finite_retention_and_non_idempotent_profiles_cannot_prove_safe_repeat(intent, kind):
    action = sent(admitted(Action(intent, "key", idempotency=kind).evaluate())).takeover()
    with pytest.raises(TransitionError):
        admitted(action, "a2", proof(action))


@pytest.mark.parametrize(
    "changes",
    [
        {"covered_attempt_ids": frozenset()},
        {"intent_digest": "changed"},
        {"account": "other"},
        {"capability": "other"},
        {"provider_key": "other"},
    ],
)
def test_safe_repetition_witness_cannot_omit_or_rebind_attempts(intent, changes):
    action = sent(
        admitted(Action(intent, "key", idempotency=Idempotency.PERMANENT).evaluate())
    ).takeover()
    with pytest.raises(TransitionError):
        admitted(action, "a2", proof(action, **changes))


def test_confirmed_effect_retains_uncertainty_for_other_attempts(intent):
    action = sent(
        admitted(Action(intent, "key", idempotency=Idempotency.PERMANENT).evaluate())
    ).takeover()
    action = sent(admitted(action, "a2", proof(action)), "a2")
    action = observe(action, E.CONFIRMED)
    assert (action.disposition, action.effect, action.reconciliation) == (
        D.CLOSED,
        E.CONFIRMED,
        R.SCHEDULED,
    )
    action = observe(action, E.CONFIRMED, attempt="a2", observation="o2")
    assert action.reconciliation is R.IDLE
    with pytest.raises(TransitionError):
        admitted(action, "a3", proof(action))


def test_distinct_extra_effect_is_conflicting_not_just_another_success(intent):
    action = sent(
        admitted(Action(intent, "key", idempotency=Idempotency.PERMANENT).evaluate())
    ).takeover()
    action = sent(admitted(action, "a2", proof(action)), "a2")
    action = observe(action, E.CONFIRMED)
    action = observe(action, E.CONFIRMED, attempt="a2", observation="o2", effect_id="effect-2")
    assert action.effect is E.CONFLICTING
    assert action.reconciliation is R.HUMAN


def test_revocation_stale_versions_and_generations(intent):
    action = admitted(Action(intent, "key").evaluate())
    revoked = action.set_authority(authorized=False, evidence_valid=True)
    with pytest.raises(TransitionError):
        revoked.cross_send_boundary(
            "a1", expected_version=action.version, generation=action.generation
        )
    with pytest.raises(TransitionError):
        admitted(revoked, "a2")
    restored = revoked.set_authority(authorized=True, evidence_valid=True)
    with pytest.raises(TransitionError):
        restored.admit("a2", expected_version=restored.version, generation=action.generation)
    assert admitted(restored, "a2").attempts[-1].generation == restored.generation


def test_c2_cannot_be_satisfied_by_c1_capability(intent):
    action = Action(replace(intent, consistency=Consistency.C2, resource_version=0), "key")
    assert action.evaluate().disposition is D.BLOCKED
    with pytest.raises(TransitionError):
        admitted(action.evaluate())


def test_cancellation_and_late_observations_do_not_reopen(intent):
    action = sent(admitted(Action(intent, "key").evaluate())).stop(close=True)
    assert action.effect is E.UNKNOWN
    assert observe(action, E.CONFIRMED).disposition is D.CLOSED
    denied_read = action.begin_reconciliation(authorized=False)
    assert denied_read.effect is E.UNKNOWN and denied_read.reconciliation is R.HUMAN


def test_final_evidence_contradiction_and_duplicate_identity(intent):
    action = sent(admitted(Action(intent, "key").evaluate()))
    observation = claim(action, E.CONFIRMED)
    action = action.observe(observation, expected_version=action.version)
    assert action.observe(observation, expected_version=action.version) is action
    action = observe(action, E.NO_EFFECT, observation="o2")
    assert action.effect is E.CONFLICTING and len(action.observations) == 2
    with pytest.raises(TransitionError):
        action.begin_reconciliation(authorized=True)


def test_explicit_conflicting_evidence_cannot_be_hidden_by_prior_finality(intent):
    action = observe(sent(admitted(Action(intent, "key").evaluate())), E.CONFIRMED)
    assert observe(action, E.CONFLICTING, observation="o2").effect is E.CONFLICTING


def test_negative_lookup_does_not_downgrade_pending_or_confirmed_evidence(intent):
    action = sent(admitted(Action(intent, "key").evaluate()))
    pending = observe(action, E.PENDING)
    assert observe(pending, E.UNKNOWN, observation="o2").effect is E.PENDING
    final = observe(pending, E.CONFIRMED, observation="o3")
    assert observe(final, E.UNKNOWN, observation="o4").effect is E.CONFIRMED


def test_no_effect_evidence_must_cover_every_possibly_sent_attempt(intent):
    action = sent(
        admitted(Action(intent, "key", idempotency=Idempotency.PERMANENT).evaluate())
    ).takeover()
    action = sent(admitted(action, "a2", proof(action)), "a2")
    action = observe(action, E.NO_EFFECT)
    assert action.effect is E.UNKNOWN
    action = observe(action, E.NO_EFFECT, attempt="a2", observation="o2")
    assert action.effect is E.NO_EFFECT
    assert admitted(action, "a3").effect is E.NO_EFFECT


def test_attempt_budget_and_unrelated_observations(intent):
    action = admitted(Action(intent, "key", max_attempts=1).evaluate()).takeover()
    with pytest.raises(TransitionError):
        admitted(action, "a2")
    with pytest.raises(TransitionError):
        action.observe(claim(action, E.CONFIRMED), expected_version=action.version)
    action = sent(admitted(Action(intent, "key").evaluate()))
    with pytest.raises(TransitionError):
        action.observe(
            replace(claim(action, E.CONFIRMED), intent_digest="other"),
            expected_version=action.version,
        )
    with pytest.raises(ValidationError):
        replace(action, authorized="yes")


def test_restored_model_snapshot_cannot_drop_repetition_coverage(intent):
    action = sent(
        admitted(Action(intent, "key", idempotency=Idempotency.PERMANENT).evaluate())
    ).takeover()
    action = admitted(action, "a2", proof(action))
    without_coverage = replace(action.attempts[-1], repetition_covered=frozenset())
    with pytest.raises(TransitionError):
        replace(action, attempts=(*action.attempts[:-1], without_coverage))
    with pytest.raises(TransitionError):
        replace(action, generation=action.generation + 1)
    with pytest.raises(ValidationError):
        action.stop(close="yes")


@pytest.mark.parametrize("first,second", [(E.NO_EFFECT, E.CONFIRMED), (E.CONFIRMED, E.NO_EFFECT)])
@pytest.mark.parametrize("same_record", [True, False])
def test_cross_attempt_final_claims_are_compared_by_provider_record(
    intent, first, second, same_record
):
    action = sent(
        admitted(Action(intent, "key", idempotency=Idempotency.PERMANENT).evaluate())
    ).takeover()
    action = sent(admitted(action, "a2", proof(action)), "a2")
    observations = (
        Observation("claim-1", "a1", intent.intent_digest, first, "record-1"),
        Observation(
            "claim-2", "a2", intent.intent_digest, second, "record-1" if same_record else "record-2"
        ),
    )
    for observation in observations:
        action = action.observe(observation, expected_version=action.version)
    assert action.observations == observations
    assert action.effect is (E.CONFLICTING if same_record else E.CONFIRMED)
    assert action.reconciliation is (R.HUMAN if same_record else R.IDLE)


@pytest.mark.parametrize("assessment", [E.UNKNOWN, E.PENDING, E.NO_EFFECT])
def test_nonterminal_observations_preserve_a_safely_admitted_retry(intent, assessment):
    action = sent(
        admitted(Action(intent, "key", idempotency=Idempotency.PERMANENT).evaluate())
    ).takeover()
    if assessment is E.PENDING:
        action = observe(action, E.PENDING, observation="initial-pending")
    action = admitted(action, "a2", proof(action))
    previous_version, generation = action.version, action.generation
    action = observe(action, assessment, observation="late-poll")
    assert action.disposition is D.ADMITTED
    assert action.effect is (E.NO_EFFECT if assessment is E.NO_EFFECT else E.UNKNOWN)
    assert action.reconciliation is R.IDLE
    assert action.generation == generation and len(action.attempts) == 2
    assert action.attempts[-1].phase is Phase.ADMITTED
    # The observation changes state version; a worker still needs a current snapshot.
    with pytest.raises(TransitionError):
        action.cross_send_boundary("a2", expected_version=previous_version, generation=generation)
    assert sent(action, "a2").attempts[-1].phase is Phase.POSSIBLY_SENT


def test_status_polling_does_not_exhaust_retry_budget_before_transmission(intent):
    action = sent(
        admitted(
            Action(intent, "key", idempotency=Idempotency.PERMANENT, max_attempts=2).evaluate()
        )
    ).takeover()
    action = admitted(action, "a2", proof(action))
    for number in range(6):
        action = observe(action, E.UNKNOWN, observation=f"poll-{number}")
        assert action.attempts[-1].phase is Phase.ADMITTED
        assert len(action.attempts) == 2
    assert sent(action, "a2").attempts[-1].phase is Phase.POSSIBLY_SENT


@pytest.mark.parametrize("assessment", [E.CONFIRMED, E.CONFLICTING])
def test_terminal_observations_still_fence_an_unsent_retry(intent, assessment):
    action = sent(
        admitted(Action(intent, "key", idempotency=Idempotency.PERMANENT).evaluate())
    ).takeover()
    action = admitted(action, "a2", proof(action))
    action = observe(action, assessment, observation="terminal")
    assert action.attempts[-1].phase is Phase.UNSENT
    assert action.disposition is not D.ADMITTED
    assert action.effect is assessment
    assert action.reconciliation is (R.HUMAN if assessment is E.CONFLICTING else R.IDLE)
    with pytest.raises(TransitionError):
        sent(action, "a2")


class LifecycleMachine(RuleBasedStateMachine):
    @initialize(profile=st.sampled_from(list(Idempotency)))
    def start(self, profile):
        intent = Intent(
            "org",
            "exec",
            "node",
            "op",
            "sim",
            "event",
            "account",
            "resource",
            1,
            None,
            Consistency.C0,
            "adapter",
            "a" * 64,
        )
        self.action = Action(intent, "key", idempotency=profile, max_attempts=8)
        self.counter = 0

    @rule(
        command=st.sampled_from(
            ["evaluate", "admit", "send", "takeover", "close", "revoke", "restore"]
        ),
        include_proof=st.booleans(),
    )
    def command(self, command, include_proof):
        before = self.action
        self.counter += 1
        try:
            match command:
                case "evaluate":
                    result = before.evaluate()
                case "admit":
                    result = admitted(
                        before, f"a{self.counter}", proof(before) if include_proof else None
                    )
                case "send":
                    result = sent(
                        before, before.attempts[-1].attempt_id if before.attempts else "absent"
                    )
                case "takeover":
                    result = before.takeover()
                case "close":
                    result = before.stop(close=True)
                case "revoke":
                    result = before.set_authority(authorized=False, evidence_valid=True)
                case "restore":
                    result = before.set_authority(authorized=True, evidence_valid=True)
            if before.disposition is D.CLOSED:
                assert result.disposition is D.CLOSED
            for old, new in zip(before.attempts, result.attempts, strict=False):
                if old.phase is Phase.POSSIBLY_SENT:
                    assert new.phase is Phase.POSSIBLY_SENT
            assert result.version > before.version
            assert result.intent is before.intent
            self.action = result
        except TransitionError:
            assert self.action is before

    @rule(effect=st.sampled_from([E.UNKNOWN, E.PENDING, E.NO_EFFECT, E.CONFIRMED, E.CONFLICTING]))
    def evidence(self, effect):
        sent_attempts = [a for a in self.action.attempts if a.phase is Phase.POSSIBLY_SENT]
        if not sent_attempts:
            return
        self.counter += 1
        self.action = observe(
            self.action,
            effect,
            attempt=sent_attempts[0].attempt_id,
            observation=f"obs{self.counter}",
        )

    @invariant()
    def uncertainty_is_preserved_and_records_are_immutable(self):
        a = self.action
        assert legal_dimensions(a.disposition, a.effect, a.reconciliation)
        assert len(a.attempts) <= a.max_attempts
        assert len({x.attempt_id for x in a.attempts}) == len(a.attempts)
        if a.effect is E.NO_EFFECT:
            assert all(
                x.assessment is E.NO_EFFECT for x in a.attempts if x.phase is Phase.POSSIBLY_SENT
            )
        if a.disposition is D.CLOSED:
            assert all(x.phase is not Phase.ADMITTED for x in a.attempts)


TestLifecycleSequences = LifecycleMachine.TestCase
TestLifecycleSequences.settings = settings(
    max_examples=80, stateful_step_count=40, deadline=None, derandomize=True, database=None
)


@pytest.mark.parametrize(
    "changes",
    [
        {"phase": "admitted"},
        {"assessment": "unknown"},
        {"phase": Phase.POSSIBLY_SENT},
        {"repetition_covered": set()},
    ],
)
def test_invalid_attempt_records_are_rejected(changes):
    with pytest.raises(ValidationError):
        Attempt("a1", 0, **changes)


@pytest.mark.parametrize(
    "changes",
    [
        {"intent": {}},
        {"idempotency": "permanent"},
        {"supported_consistency": {Consistency.C0}},
        {"supported_consistency": frozenset({"C0"})},
        {"effect": E.UNKNOWN},
        {"attempts": []},
        {"observations": []},
        {"attempts": ({},)},
        {"observations": ({},)},
        {"disposition": D.ADMITTED},
        {"attempts": (Attempt("a1", 0, Phase.UNSENT),)},
        {"attempts": (Attempt("a1", 0),)},
    ],
)
def test_invalid_restored_action_records_are_rejected(intent, changes):
    with pytest.raises((ValidationError, TransitionError)):
        replace(Action(intent, "key"), **changes)


@pytest.mark.parametrize(
    "changes",
    [
        {"attempts": (Attempt("a1", 0), Attempt("a1", 0))},
        {"attempts": (Attempt("a1", 0), Attempt("a2", 0))},
        {"attempts": (Attempt("a1", 0), Attempt("a2", 0, Phase.UNSENT))},
        {"attempts": (Attempt("a1", 0, Phase.UNSENT),)},
    ],
)
def test_restored_active_state_cannot_duplicate_or_displace_attempts(intent, changes):
    with pytest.raises(TransitionError):
        replace(admitted(Action(intent, "key").evaluate()), **changes)


@pytest.mark.parametrize(
    "effect,reconciliation",
    [
        (E.NOT_ATTEMPTED, R.IDLE),
        (E.NO_EFFECT, R.IDLE),
        (E.CONFIRMED, R.IDLE),
        (E.CONFLICTING, R.HUMAN),
    ],
)
def test_restored_effect_requires_supporting_attempt_facts(intent, effect, reconciliation):
    action = sent(admitted(Action(intent, "key").evaluate()))
    with pytest.raises(TransitionError):
        replace(action, disposition=D.CLOSED, effect=effect, reconciliation=reconciliation)


def test_invalid_observations_and_closed_commands_are_rejected(intent):
    with pytest.raises(ValidationError):
        Observation("o1", "a1", intent.intent_digest, E.NOT_ATTEMPTED)
    closed = Action(intent, "key").stop(close=True)
    with pytest.raises(TransitionError):
        closed.evaluate()
    with pytest.raises(TransitionError):
        closed.stop()
    with pytest.raises(TransitionError):
        closed.begin_reconciliation(authorized=True)
    pending = sent(admitted(Action(intent, "key").evaluate())).takeover()
    with pytest.raises(ValidationError):
        pending.begin_reconciliation(authorized="yes")
