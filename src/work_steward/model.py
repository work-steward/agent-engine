"""Immutable in-memory reference semantics, not a durable authorization controller.

Authority and observation inputs are trusted model events. A future controller must
derive them from authoritative policy and admissible evidence, never caller assertions.
"""

from dataclasses import dataclass, replace
from enum import StrEnum

from .canonical import ValidationError, integer, text
from .intent import Consistency, Intent


class TransitionError(ValueError):
    """A model command violates a transition guard."""


class Disposition(StrEnum):
    PROPOSED = "proposed"
    BLOCKED = "blocked"
    ELIGIBLE = "eligible"
    ADMITTED = "attempt_admitted"
    PAUSED = "paused"
    CLOSED = "closed"


class Effect(StrEnum):
    NOT_ATTEMPTED = "not_attempted"
    UNKNOWN = "unknown"
    PENDING = "pending"
    NO_EFFECT = "no_effect_confirmed"
    CONFIRMED = "effect_confirmed"
    CONFLICTING = "conflicting"


class Reconciliation(StrEnum):
    IDLE = "idle"
    SCHEDULED = "scheduled"
    INVESTIGATING = "investigating"
    HUMAN = "awaiting_human"


class Phase(StrEnum):
    ADMITTED = "admitted"
    UNSENT = "closed_without_send"
    POSSIBLY_SENT = "send_possible"


class Idempotency(StrEnum):
    NONE = "none"
    PERMANENT = "permanent"
    FINITE = "finite"


def legal_dimensions(d: Disposition, e: Effect, r: Reconciliation) -> bool:
    """Closed relation from the reviewed profile, independent of attempt guards."""
    if type(d) is not Disposition or type(e) is not Effect or type(r) is not Reconciliation:
        return False
    if d is Disposition.PROPOSED:
        return e is Effect.NOT_ATTEMPTED and r is Reconciliation.IDLE
    if d in (Disposition.BLOCKED, Disposition.ELIGIBLE):
        return e in (Effect.NOT_ATTEMPTED, Effect.NO_EFFECT) and r is Reconciliation.IDLE
    if d is Disposition.ADMITTED:
        return (
            e in (Effect.NOT_ATTEMPTED, Effect.NO_EFFECT, Effect.UNKNOWN)
            and r is Reconciliation.IDLE
        )
    if e is Effect.CONFLICTING:
        return r is Reconciliation.HUMAN
    if e in (Effect.UNKNOWN, Effect.PENDING):
        return r in (Reconciliation.SCHEDULED, Reconciliation.INVESTIGATING, Reconciliation.HUMAN)
    if e is Effect.CONFIRMED:
        return d is Disposition.CLOSED
    if d is Disposition.CLOSED:
        return r is Reconciliation.IDLE
    return r in (Reconciliation.IDLE, Reconciliation.HUMAN)


@dataclass(frozen=True)
class Attempt:
    attempt_id: str
    generation: int
    phase: Phase = Phase.ADMITTED
    assessment: Effect = Effect.NOT_ATTEMPTED
    repetition_covered: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        text(self.attempt_id, "attempt_id")
        integer(self.generation, "attempt generation")
        if type(self.phase) is not Phase or type(self.assessment) is not Effect:
            raise ValidationError("Invalid attempt phase or assessment")
        if (self.phase is Phase.POSSIBLY_SENT) == (self.assessment is Effect.NOT_ATTEMPTED):
            raise ValidationError("Attempt phase and assessment disagree")
        if type(self.repetition_covered) is not frozenset:
            raise ValidationError("Repetition coverage must be immutable")


@dataclass(frozen=True)
class Observation:
    observation_id: str
    attempt_id: str
    intent_digest: str
    assessment: Effect
    provider_effect_id: str | None = None

    def __post_init__(self) -> None:
        text(self.observation_id, "observation_id")
        text(self.attempt_id, "attempt_id")
        if type(self.assessment) is not Effect or self.assessment is Effect.NOT_ATTEMPTED:
            raise ValidationError("Unsupported observation assessment")
        if self.provider_effect_id is not None or self.assessment is Effect.CONFIRMED:
            text(self.provider_effect_id, "provider_effect_id")


@dataclass(frozen=True)
class RepetitionProof:
    """Model witness for permanent keyed deduplication; not a provider attestation."""

    intent_digest: str
    covered_attempt_ids: frozenset[str]
    account: str
    capability: str
    provider_key: str


@dataclass(frozen=True)
class Action:
    intent: Intent
    provider_key: str
    idempotency: Idempotency = Idempotency.NONE
    supported_consistency: frozenset[Consistency] = frozenset({Consistency.C0, Consistency.C1})
    max_attempts: int = 3
    version: int = 0
    generation: int = 0
    authorized: bool = True
    evidence_valid: bool = True
    disposition: Disposition = Disposition.PROPOSED
    effect: Effect = Effect.NOT_ATTEMPTED
    reconciliation: Reconciliation = Reconciliation.IDLE
    attempts: tuple[Attempt, ...] = ()
    observations: tuple[Observation, ...] = ()

    def __post_init__(self) -> None:
        if type(self.intent) is not Intent or type(self.idempotency) is not Idempotency:
            raise ValidationError("Invalid intent or capability profile")
        text(self.provider_key, "provider_key")
        integer(self.max_attempts, "max_attempts", minimum=1)
        integer(self.version, "version")
        integer(self.generation, "generation")
        if type(self.authorized) is not bool or type(self.evidence_valid) is not bool:
            raise ValidationError("Authority facts must be typed booleans")
        if type(self.supported_consistency) is not frozenset or any(
            type(c) is not Consistency for c in self.supported_consistency
        ):
            raise ValidationError("Unsupported consistency capability set")
        if not legal_dimensions(self.disposition, self.effect, self.reconciliation):
            raise TransitionError("Illegal operation state combination")
        if type(self.attempts) is not tuple or type(self.observations) is not tuple:
            raise ValidationError("Model records must be immutable tuples")
        if any(type(a) is not Attempt for a in self.attempts) or any(
            type(o) is not Observation for o in self.observations
        ):
            raise ValidationError("Invalid model record type")
        if len({a.attempt_id for a in self.attempts}) != len(self.attempts):
            raise TransitionError("Attempt identity cannot be reused")
        active = [a for a in self.attempts if a.phase is Phase.ADMITTED]
        if len(active) > 1 or len(self.attempts) > self.max_attempts:
            raise TransitionError("Active attempt or attempt-budget violation")
        if active and (
            self.disposition is not Disposition.ADMITTED or active[0] != self.attempts[-1]
        ):
            raise TransitionError("Only the current admitted attempt can remain active")
        if self.disposition is Disposition.PROPOSED and self.attempts:
            raise TransitionError("Proposed operation cannot have attempts")
        if self.disposition is Disposition.ADMITTED and (
            not self.attempts or self.attempts[-1].phase is Phase.UNSENT
        ):
            raise TransitionError("Admitted operation needs a current attempt")
        sent = [a for a in self.attempts if a.phase is Phase.POSSIBLY_SENT]
        if self.effect is Effect.NOT_ATTEMPTED and sent:
            raise TransitionError("Possibly sent attempts cannot be not_attempted")
        if self.effect is Effect.NO_EFFECT and (
            not sent or any(a.assessment is not Effect.NO_EFFECT for a in sent)
        ):
            raise TransitionError("No-effect finality must cover all sent attempts")
        if self.effect is Effect.CONFIRMED and not any(
            a.assessment is Effect.CONFIRMED for a in sent
        ):
            raise TransitionError("Confirmed effect requires a confirmed attempt")
        if self.effect in (Effect.UNKNOWN, Effect.PENDING) and not any(
            a.assessment in (Effect.UNKNOWN, Effect.PENDING) for a in sent
        ):
            raise TransitionError("Uncertain effect requires an unresolved sent attempt")
        if self.effect is Effect.CONFLICTING and not any(
            a.assessment is Effect.CONFLICTING for a in sent
        ):
            raise TransitionError("Conflict requires retained conflicting attempt evidence")
        if active:
            current = active[0]
            previous = [a for a in sent if a.assessment is not Effect.NO_EFFECT]
            if current.generation != self.generation:
                raise TransitionError("Active attempt belongs to a stale generation")
            if previous and (
                self.idempotency is not Idempotency.PERMANENT
                or current.repetition_covered != frozenset(a.attempt_id for a in sent)
            ):
                raise TransitionError("Active repetition lacks complete permanent-key coverage")

    def _change(self, **changes: object) -> "Action":
        return replace(self, version=self.version + 1, **changes)

    def _check_version(self, expected_version: int) -> None:
        if type(expected_version) is not int or expected_version != self.version:
            raise TransitionError("Stale authoritative state version")

    def _eligible(self) -> bool:
        return (
            self.authorized
            and self.evidence_valid
            and self.intent.consistency in self.supported_consistency
        )

    def _fenced(self) -> tuple[Attempt, ...]:
        return tuple(
            replace(a, phase=Phase.UNSENT) if a.phase is Phase.ADMITTED else a
            for a in self.attempts
        )

    def evaluate(self) -> "Action":
        if self.disposition in (Disposition.CLOSED, Disposition.ADMITTED):
            raise TransitionError("Cannot evaluate a closed or active operation")
        if self.effect in (Effect.UNKNOWN, Effect.PENDING, Effect.CONFLICTING):
            raise TransitionError("Uncertain operation requires reconciliation or safe repetition")
        return self._change(
            disposition=Disposition.ELIGIBLE if self._eligible() else Disposition.BLOCKED,
            reconciliation=Reconciliation.IDLE,
        )

    def set_authority(self, *, authorized: bool, evidence_valid: bool) -> "Action":
        """Trusted model event; a production policy reader is not implemented."""
        action = self.stop() if self.disposition is not Disposition.CLOSED else self
        return action._change(authorized=authorized, evidence_valid=evidence_valid)

    def admit(
        self,
        attempt_id: str,
        *,
        expected_version: int,
        generation: int,
        proof: RepetitionProof | None = None,
    ) -> "Action":
        self._check_version(expected_version)
        text(attempt_id, "attempt_id")
        if type(generation) is not int or generation != self.generation or not self._eligible():
            raise TransitionError("Stale worker or ineligible current authority/capability")
        if self.disposition not in (Disposition.ELIGIBLE, Disposition.PAUSED):
            raise TransitionError(
                "Admission requires eligible or safely repeatable paused operation"
            )
        if self.effect is Effect.CONFLICTING or any(
            a.phase is Phase.ADMITTED for a in self.attempts
        ):
            raise TransitionError("Conflicting evidence or an active attempt blocks admission")
        if len(self.attempts) >= self.max_attempts or any(
            a.attempt_id == attempt_id for a in self.attempts
        ):
            raise TransitionError("Attempt budget exhausted or identity reused")
        sent = frozenset(a.attempt_id for a in self.attempts if a.phase is Phase.POSSIBLY_SENT)
        unresolved = any(
            a.phase is Phase.POSSIBLY_SENT and a.assessment is not Effect.NO_EFFECT
            for a in self.attempts
        )
        if unresolved and not (
            type(proof) is RepetitionProof
            and self.idempotency is Idempotency.PERMANENT
            and type(proof.covered_attempt_ids) is frozenset
            and proof.covered_attempt_ids == sent
            and proof.intent_digest == self.intent.intent_digest
            and proof.account == self.intent.account
            and proof.capability == self.intent.capability
            and proof.provider_key == self.provider_key
        ):
            raise TransitionError("Missing or invalid safe-repetition evidence")
        new = Attempt(
            attempt_id, generation, repetition_covered=sent if unresolved else frozenset()
        )
        return self._change(
            attempts=self.attempts + (new,),
            disposition=Disposition.ADMITTED,
            effect=Effect.UNKNOWN if unresolved else self.effect,
            reconciliation=Reconciliation.IDLE,
        )

    def cross_send_boundary(
        self, attempt_id: str, *, expected_version: int, generation: int
    ) -> "Action":
        self._check_version(expected_version)
        if not self._eligible() or type(generation) is not int or generation != self.generation:
            raise TransitionError("Authority changed or worker is stale")
        if self.disposition is not Disposition.ADMITTED or not self.attempts:
            raise TransitionError("No admitted attempt")
        current = self.attempts[-1]
        if current.attempt_id != attempt_id or current.phase is not Phase.ADMITTED:
            raise TransitionError("Send boundary is single-use for the current attempt")
        current = replace(current, phase=Phase.POSSIBLY_SENT, assessment=Effect.UNKNOWN)
        return self._change(attempts=self.attempts[:-1] + (current,), effect=Effect.UNKNOWN)

    def stop(self, *, close: bool = False) -> "Action":
        """Fence unsent attempts; do not pretend a released sender was recalled."""
        if type(close) is not bool:
            raise ValidationError("Close command must use a typed boolean")
        if self.disposition is Disposition.CLOSED and not close:
            raise TransitionError("Closed operations cannot reopen")
        d = (
            Disposition.CLOSED
            if close or self.disposition is Disposition.CLOSED
            else Disposition.PAUSED
        )
        r = (
            Reconciliation.HUMAN
            if self.effect is Effect.CONFLICTING
            else Reconciliation.SCHEDULED
            if self.effect in (Effect.UNKNOWN, Effect.PENDING)
            else self.reconciliation
            if self.effect is Effect.CONFIRMED
            else Reconciliation.IDLE
        )
        return self._change(
            attempts=self._fenced(), disposition=d, reconciliation=r, generation=self.generation + 1
        )

    def takeover(self) -> "Action":
        return self.stop(close=self.disposition is Disposition.CLOSED)

    def begin_reconciliation(self, *, authorized: bool) -> "Action":
        if self.reconciliation not in (Reconciliation.SCHEDULED, Reconciliation.HUMAN):
            raise TransitionError("No outstanding reconciliation")
        if self.effect is Effect.CONFLICTING:
            raise TransitionError("Conflicting evidence requires human handling in this profile")
        if type(authorized) is not bool:
            raise ValidationError("Read authority must be a typed fact")
        return self._change(
            reconciliation=Reconciliation.INVESTIGATING if authorized else Reconciliation.HUMAN
        )

    def observe(self, observation: Observation, *, expected_version: int) -> "Action":
        self._check_version(expected_version)
        if (
            type(observation) is not Observation
            or observation.intent_digest != self.intent.intent_digest
        ):
            raise TransitionError("Observation is not bound to this immutable intent")
        if observation in self.observations:
            return self
        attempts = list(self.attempts)
        matches = [i for i, a in enumerate(attempts) if a.attempt_id == observation.attempt_id]
        if not matches or attempts[matches[0]].phase is not Phase.POSSIBLY_SENT:
            raise TransitionError("Observation must refer to an originally possibly sent attempt")
        i = matches[0]
        previous = attempts[i].assessment
        incoming = observation.assessment
        finals = {Effect.CONFIRMED, Effect.NO_EFFECT}
        prior_effects = {
            o.provider_effect_id for o in self.observations if o.assessment is Effect.CONFIRMED
        }
        extra_effect = incoming is Effect.CONFIRMED and bool(
            prior_effects - {observation.provider_effect_id}
        )
        provider_record_conflict = (
            incoming in finals
            and observation.provider_effect_id is not None
            and any(
                o.provider_effect_id == observation.provider_effect_id
                and o.assessment in finals
                and o.assessment is not incoming
                for o in self.observations
            )
        )
        if (
            (
                incoming is Effect.CONFLICTING
                or extra_effect
                or provider_record_conflict
                or any(o.observation_id == observation.observation_id for o in self.observations)
            )
            or (previous in finals and incoming in finals and previous != incoming)
            or previous is Effect.CONFLICTING
        ):
            outcome = Effect.CONFLICTING
        elif previous in finals or previous is Effect.PENDING and incoming is Effect.UNKNOWN:
            outcome = previous
        else:
            outcome = incoming
        attempts[i] = replace(attempts[i], assessment=outcome)
        attempts = tuple(attempts)
        outcomes = {a.assessment for a in attempts if a.phase is Phase.POSSIBLY_SENT}
        d = Disposition.CLOSED if self.disposition is Disposition.CLOSED else Disposition.PAUSED
        if Effect.CONFLICTING in outcomes:
            e, r = Effect.CONFLICTING, Reconciliation.HUMAN
        elif Effect.CONFIRMED in outcomes:
            e, d = Effect.CONFIRMED, Disposition.CLOSED
            r = (
                Reconciliation.SCHEDULED
                if outcomes & {Effect.UNKNOWN, Effect.PENDING}
                else Reconciliation.IDLE
            )
        elif outcomes & {Effect.UNKNOWN, Effect.PENDING}:
            e = Effect.PENDING if Effect.PENDING in outcomes else Effect.UNKNOWN
            r = Reconciliation.SCHEDULED
        else:
            e, r = Effect.NO_EFFECT, Reconciliation.IDLE
        keep_admitted_retry = (
            any(a.phase is Phase.ADMITTED for a in attempts)
            and self._eligible()
            and e not in (Effect.CONFIRMED, Effect.CONFLICTING)
        )
        if keep_admitted_retry:
            # An old nonterminal observation does not invalidate permanent-key coverage.
            # Its version still changes, so the worker must re-read before crossing the boundary.
            d, r = Disposition.ADMITTED, Reconciliation.IDLE
            if e is Effect.PENDING:
                e = Effect.UNKNOWN  # Same projection used when the retry was admitted.
        else:
            attempts = tuple(
                replace(a, phase=Phase.UNSENT) if a.phase is Phase.ADMITTED else a for a in attempts
            )
        return self._change(
            attempts=attempts,
            observations=self.observations + (observation,),
            disposition=d,
            effect=e,
            reconciliation=r,
        )
