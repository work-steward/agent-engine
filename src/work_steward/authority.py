"""Local authority control. Caller identity and evidence provenance must be trusted."""

import re
import time
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import asdict, dataclass, fields
from pathlib import Path

from .canonical import ValidationError, canonical_bytes, closed_object, integer, parse_json, text
from .intent import EvidenceRef
from .ledger import Ledger, LedgerConflict, LedgerMode
from .model import Action, Disposition, Effect, TransitionError


class AuthorizationDenied(ValueError):
    """Current policy, approval, evidence, role, or time denies authority."""


@dataclass(frozen=True)
class Policy:
    account: str
    capability: str
    adapter_id: str
    adapter_digest: str
    resources: frozenset[str]
    approvers: frozenset[str]
    max_quantity: int
    approval_ttl_seconds: int = 3600
    required_evidence: frozenset[str] = frozenset()

    def __post_init__(self):
        for name in ("account", "capability", "adapter_id"):
            text(getattr(self, name), name)
        if type(self.adapter_digest) is not str or not re.fullmatch(
            "[0-9a-f]{64}", self.adapter_digest
        ):
            raise ValidationError("Adapter digest must be SHA-256 hex")
        for name in ("resources", "approvers", "required_evidence"):
            value = getattr(self, name)
            if (
                type(value) is not frozenset
                or len(value) > 32
                or (name != "required_evidence" and not value)
            ):
                raise ValidationError(
                    "Policy sets must be immutable, bounded, and explicitly scoped"
                )
            for item in value:
                text(item, name)
        integer(self.max_quantity, "max_quantity", minimum=1)
        integer(self.approval_ttl_seconds, "approval_ttl_seconds", minimum=1)
        if self.approval_ttl_seconds > 86400:
            raise ValidationError("Approval lifetime exceeds one day")

    @property
    def canonical(self) -> bytes:
        value = asdict(self)
        for name in ("resources", "approvers", "required_evidence"):
            value[name] = sorted(value[name])
        return canonical_bytes(value)

    @classmethod
    def from_json(cls, value: bytes) -> "Policy":
        record = closed_object(parse_json(value), {field.name for field in fields(cls)})
        for name in ("resources", "approvers", "required_evidence"):
            items = record[name]
            if (
                type(items) is not list
                or any(type(item) is not str for item in items)
                or len(set(items)) != len(items)
            ):
                raise ValidationError("Invalid policy set")
            record[name] = frozenset(items)
        return cls(**record)


class Authority:
    def __init__(
        self,
        path: Path,
        *,
        organization_id: str,
        administrators: frozenset[str],
        clock: Callable[[], int] | None = None,
    ):
        if type(administrators) is not frozenset or not 1 <= len(administrators) <= 32:
            raise ValidationError("Explicit administrators are required")
        for actor in administrators:
            text(actor, "administrator")
        if clock is not None and not callable(clock):
            raise ValidationError("Clock must be a trusted callable")
        self.ledger = Ledger(path, organization_id=organization_id, mode=LedgerMode.GOVERNED)
        self._clock = clock if clock is not None else (lambda: time.time_ns() // 1_000_000_000)
        self._administrators = administrators
        binding = canonical_bytes(sorted(administrators))
        with self.ledger._transaction(write=True) as db:
            row = db.execute(
                "SELECT administrators FROM authority_config WHERE singleton=1"
            ).fetchone()
            if row is None:
                db.execute("INSERT INTO authority_config VALUES (1,?,0)", (binding,))
            elif row[0] != binding:
                raise LedgerConflict("Administrator binding cannot be replaced on restart")

    @contextmanager
    def _write(self):
        denied = None
        with self.ledger._transaction(write=True) as db:
            now = self._clock()
            integer(now, "clock")
            floor = db.execute(
                "SELECT last_tick FROM authority_config WHERE singleton=1"
            ).fetchone()[0]
            if now < floor:
                raise AuthorizationDenied("Clock moved backwards")
            db.execute("UPDATE authority_config SET last_tick=? WHERE singleton=1", (now,))
            db.execute("SAVEPOINT authority_command")
            try:
                yield db, now
            except AuthorizationDenied as error:
                db.execute("ROLLBACK TO authority_command")
                db.execute(
                    "INSERT INTO authority_denials(at,reason) VALUES (?,?)", (now, str(error))
                )
                denied = error
            finally:
                db.execute("RELEASE authority_command")
        # Retain observed time on denial so a clock rollback cannot revive expired grants.
        if denied is not None:
            raise denied

    def _admin(self, actor: str):
        text(actor, "actor")
        if actor not in self._administrators:
            raise AuthorizationDenied("Administrator permission required")

    @staticmethod
    def _policy(db) -> tuple[int, Policy]:
        row = db.execute(
            "SELECT revision,value FROM policies ORDER BY revision DESC LIMIT 1"
        ).fetchone()
        if row is None:
            raise AuthorizationDenied("No active policy")
        return row[0], Policy.from_json(row[1])

    def configure(self, policy: Policy, *, actor: str, expected_revision: int) -> int:
        if type(policy) is not Policy:
            raise ValidationError("A typed policy is required")
        integer(expected_revision, "expected_revision")
        with self._write() as (db, now):
            self._admin(actor)
            revision = db.execute("SELECT coalesce(max(revision),0) FROM policies").fetchone()[0]
            if revision != expected_revision:
                raise LedgerConflict("Stale policy revision")
            integer(revision + 1, "policy revision")
            db.execute(
                "INSERT INTO policies VALUES (?,?,?,?)",
                (revision + 1, policy.canonical, actor, now),
            )
        return revision + 1

    def record_evidence(
        self,
        reference: EvidenceRef,
        *,
        account: str,
        capability: str,
        expires_at: int,
        actor: str,
        expected_revision: int,
    ) -> int:
        if type(reference) is not EvidenceRef:
            raise ValidationError("A typed evidence reference is required")
        text(account, "account")
        text(capability, "capability")
        integer(expires_at, "expires_at")
        integer(expected_revision, "expected_revision")
        with self._write() as (db, now):
            self._admin(actor)
            if expires_at <= now:
                raise AuthorizationDenied("Evidence is already expired")
            revision = db.execute(
                "SELECT coalesce(max(revision),0) FROM evidence "
                "WHERE account=? AND capability=? AND subject=? AND predicate=?",
                (account, capability, reference.subject, reference.predicate),
            ).fetchone()[0]
            if revision != expected_revision:
                raise LedgerConflict("Stale evidence revision")
            integer(revision + 1, "evidence revision")
            db.execute(
                "INSERT INTO evidence(account,capability,subject,predicate,"
                "material_version,revision,expires_at,actor,at) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    account,
                    capability,
                    reference.subject,
                    reference.predicate,
                    reference.material_version,
                    revision + 1,
                    expires_at,
                    actor,
                    now,
                ),
            )
        return revision + 1

    @staticmethod
    def _scope(db, action: Action, policy: Policy, now: int):
        intent = action.intent
        if (
            intent.account != policy.account
            or intent.capability != policy.capability
            or intent.adapter_id != policy.adapter_id
            or intent.adapter_digest != policy.adapter_digest
            or intent.resource not in policy.resources
            or intent.quantity > policy.max_quantity
            or intent.consistency not in action.supported_consistency
        ):
            raise AuthorizationDenied("Intent is outside policy scope or capability support")
        references = {(ref.subject, ref.predicate) for ref in intent.evidence_refs}
        if any(
            (intent.resource, predicate) not in references for predicate in policy.required_evidence
        ):
            raise AuthorizationDenied("Required evidence is missing")
        for reference in intent.evidence_refs:
            row = db.execute(
                "SELECT material_version,expires_at FROM evidence "
                "WHERE account=? AND capability=? AND subject=? AND predicate=? "
                "ORDER BY revision DESC LIMIT 1",
                (intent.account, intent.capability, reference.subject, reference.predicate),
            ).fetchone()
            if row is None or row[0] != reference.material_version or row[1] <= now:
                raise AuthorizationDenied("Evidence is missing, changed, or expired")

    @staticmethod
    def _approval(db, operation_id: str):
        return db.execute(
            "SELECT * FROM approvals WHERE operation_id=? ORDER BY sequence DESC LIMIT 1",
            (operation_id,),
        ).fetchone()

    def approve(
        self, operation_id: str, *, approval_id: str, actor: str, expires_at: int
    ) -> Action:
        text(operation_id, "operation_id")
        text(approval_id, "approval_id")
        text(actor, "actor")
        integer(expires_at, "expires_at")
        with self._write() as (db, now):
            before = self.ledger._load(db, operation_id)
            revision, policy = self._policy(db)
            if actor not in policy.approvers:
                raise AuthorizationDenied("Approver permission required")
            old = db.execute(
                "SELECT * FROM approvals WHERE approval_id=?", (approval_id,)
            ).fetchone()
            if old is not None:
                if (
                    old["operation_id"],
                    old["intent_digest"],
                    old["policy_revision"],
                    old["actor"],
                    old["expires_at"],
                ) != (operation_id, before.intent.intent_digest, revision, actor, expires_at):
                    raise LedgerConflict("Approval identity has another immutable binding")
                return before
            if before.disposition is Disposition.CLOSED or before.effect is Effect.CONFLICTING:
                raise AuthorizationDenied("Closed or conflicting operations cannot be approved")
            if not now < expires_at <= now + policy.approval_ttl_seconds:
                raise AuthorizationDenied("Approval expiry is outside policy bounds")
            self._scope(db, before, policy, now)
            db.execute(
                "INSERT INTO approvals(approval_id,operation_id,intent_digest,policy_revision,"
                "actor,issued_at,expires_at) "
                "VALUES (?,?,?,?,?,?,?)",
                (
                    approval_id,
                    operation_id,
                    before.intent.intent_digest,
                    revision,
                    actor,
                    now,
                    expires_at,
                ),
            )
            after = before.set_authority(authorized=True, evidence_valid=True)
            if after.effect in (Effect.NOT_ATTEMPTED, Effect.NO_EFFECT):
                after = after.evaluate()
            self._save(
                db,
                before,
                after,
                "approve",
                {
                    "approval_id": approval_id,
                    "actor": actor,
                    "policy_revision": revision,
                    "at": now,
                },
            )
        return after

    def revoke(self, approval_id: str, *, actor: str, reason: str) -> Action:
        text(approval_id, "approval_id")
        text(actor, "actor")
        text(reason, "reason")
        with self._write() as (db, now):
            grant = db.execute(
                "SELECT * FROM approvals WHERE approval_id=?", (approval_id,)
            ).fetchone()
            if grant is None:
                raise LedgerConflict("Unknown approval")
            if actor not in self._administrators and actor != grant["actor"]:
                raise AuthorizationDenied("Approval owner or administrator permission required")
            before = self.ledger._load(db, grant["operation_id"])
            if db.execute(
                "SELECT 1 FROM revocations WHERE approval_id=?", (approval_id,)
            ).fetchone():
                return before
            db.execute(
                "INSERT INTO revocations VALUES (?,?,?,?)", (approval_id, actor, reason, now)
            )
            current = self._approval(db, grant["operation_id"])
            after = (
                before.set_authority(authorized=False, evidence_valid=before.evidence_valid)
                if current["approval_id"] == approval_id
                else before
            )
            if after is not before:
                self._save(
                    db,
                    before,
                    after,
                    "revoke",
                    {"approval_id": approval_id, "actor": actor, "reason": reason, "at": now},
                )
        return after

    def _execute(
        self,
        operation_id: str,
        *,
        expected_version: int,
        generation: int,
        attempt_id: str,
        send: bool,
    ) -> Action:
        text(operation_id, "operation_id")
        integer(expected_version, "expected_version")
        with self._write() as (db, now):
            before = self.ledger._load(db, operation_id)
            if before.version != expected_version:
                raise TransitionError("Stale authoritative state version")
            revision, policy = self._policy(db)
            grant = self._approval(db, operation_id)
            if (
                grant is None
                or grant["intent_digest"] != before.intent.intent_digest
                or grant["policy_revision"] != revision
                or grant["expires_at"] <= now
                or db.execute(
                    "SELECT 1 FROM revocations WHERE approval_id=?", (grant["approval_id"],)
                ).fetchone()
            ):
                raise AuthorizationDenied("Current approval is missing, expired, revoked, or stale")
            self._scope(db, before, policy, now)
            method = before.cross_send_boundary if send else before.admit
            after = method(attempt_id, expected_version=expected_version, generation=generation)
            self._save(
                db,
                before,
                after,
                "send_possible" if send else "admit",
                {
                    "attempt_id": attempt_id,
                    "generation": generation,
                    "approval_id": grant["approval_id"],
                    "policy_revision": revision,
                    "at": now,
                },
            )
        return after

    def admit(
        self, operation_id: str, *, expected_version: int, generation: int, attempt_id: str
    ) -> Action:
        return self._execute(
            operation_id,
            expected_version=expected_version,
            generation=generation,
            attempt_id=attempt_id,
            send=False,
        )

    def mark_send_possible(
        self, operation_id: str, *, expected_version: int, generation: int, attempt_id: str
    ) -> Action:
        """Persist the boundary; no transport is exposed by this controller."""
        return self._execute(
            operation_id,
            expected_version=expected_version,
            generation=generation,
            attempt_id=attempt_id,
            send=True,
        )

    @staticmethod
    def _save(db, before: Action, after: Action, command: str, data: dict):
        Ledger._store_change(db, before, after)
        Ledger._journal(db, after, command, before.version, canonical_bytes(data))
