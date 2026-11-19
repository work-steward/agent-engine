"""SQLite operations, retained reservations, and atomic journal commits."""

import sqlite3
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path

from .canonical import ValidationError, canonical_bytes, integer, parse_json, text
from .intent import Consistency, Intent
from .ledger_schema import (
    APPLICATION_ID,
    AUTHORITY_IMMUTABLE,
    AUTHORITY_SCHEMA,
    IMMUTABLE_TABLES,
    SCHEMA,
    SCHEMA_VERSION,
)
from .model import (
    Action,
    Attempt,
    Disposition,
    Effect,
    Idempotency,
    Observation,
    Phase,
    Reconciliation,
    RepetitionProof,
    TransitionError,
)


class LedgerConflict(ValueError):
    """An immutable binding or reserved business effect belongs to another submission."""


class LedgerFormatError(ValueError):
    """The database has another owner, application, or unsupported schema version."""


class OperationNotFound(KeyError):
    """The operation is absent from this organization's ledger."""


class Command(StrEnum):
    EVALUATE = "evaluate"
    SET_AUTHORITY = "set_authority"
    ADMIT = "admit"
    SEND_POSSIBLE = "send_possible"
    STOP = "stop"
    TAKEOVER = "takeover"
    OBSERVE = "observe"
    BEGIN_RECONCILIATION = "begin_reconciliation"


class LedgerMode(StrEnum):
    REFERENCE = "reference"
    GOVERNED = "governed"


@dataclass(frozen=True)
class JournalEntry:
    sequence: int
    operation_id: str
    command: str
    previous_version: int | None
    version: int
    generation: int
    disposition: Disposition
    effect: Effect
    reconciliation: Reconciliation
    data: bytes


def _command_data(arguments: dict) -> bytes:
    value = dict(arguments)
    for name, argument in value.items():
        if type(argument) is Observation:
            value[name] = {**asdict(argument), "assessment": argument.assessment.value}
        elif type(argument) is RepetitionProof:
            value[name] = {
                **asdict(argument),
                "covered_attempt_ids": sorted(argument.covered_attempt_ids),
            }
    return canonical_bytes(value)


class Ledger:
    def __init__(
        self,
        path: Path,
        *,
        organization_id: str,
        busy_timeout_ms: int = 2000,
        mode: LedgerMode = LedgerMode.REFERENCE,
    ):
        text(organization_id, "organization_id")
        integer(busy_timeout_ms, "busy_timeout_ms", minimum=1)
        if type(mode) is not LedgerMode:
            raise ValidationError("Use a supported ledger mode")
        if busy_timeout_ms > 60_000 or str(path) == ":memory:":
            raise ValidationError("Use a local database file and a bounded lock timeout")
        self.path = Path(path).resolve()
        self.organization_id = organization_id
        self.busy_timeout_ms = busy_timeout_ms
        self.mode = mode
        with self._transaction(write=True, initialize=True):
            pass

    @contextmanager
    def _transaction(self, *, write: bool = False, initialize: bool = False):
        if sqlite3.sqlite_version_info < (3, 37, 0):
            raise RuntimeError("SQLite 3.37 or later is required")
        db = sqlite3.connect(self.path, isolation_level=None, timeout=self.busy_timeout_ms / 1000)
        db.row_factory = sqlite3.Row
        try:
            # Reject an unrelated database before changing its persistent journal mode.
            self._check_application(db, allow_empty=initialize, allow_legacy=initialize)
            db.execute("PRAGMA foreign_keys=ON")
            mode = db.execute("PRAGMA journal_mode=WAL").fetchone()[0]
            db.execute("PRAGMA synchronous=FULL")
            if (
                mode != "wal"
                or db.execute("PRAGMA synchronous").fetchone()[0] != 2
                or db.execute("PRAGMA foreign_keys").fetchone()[0] != 1
            ):
                raise RuntimeError("Required ledger durability settings unavailable")
            db.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            if initialize:
                self._initialize(db)
            self._check_database(db)
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def _initialize(self, db: sqlite3.Connection) -> None:
        self._check_application(db, allow_empty=True, allow_legacy=True)
        application = db.execute("PRAGMA application_id").fetchone()[0]
        version = db.execute("PRAGMA user_version").fetchone()[0]
        if application == APPLICATION_ID and version == 1:
            if self.mode is not LedgerMode.REFERENCE:
                raise LedgerFormatError("Reference databases cannot become governed databases")
            db.execute(
                "ALTER TABLE ledger_meta ADD COLUMN mode TEXT NOT NULL DEFAULT 'reference' "
                "CHECK(mode IN ('reference','governed'))"
            )
            for sql in AUTHORITY_SCHEMA:
                db.execute(sql)
            self._retain(db, AUTHORITY_IMMUTABLE)
            db.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
        if application == 0:
            for sql in (*SCHEMA, *AUTHORITY_SCHEMA):
                db.execute(sql)
            self._retain(db, (*IMMUTABLE_TABLES, *AUTHORITY_IMMUTABLE))
            db.execute(
                "INSERT INTO ledger_meta VALUES (1,?,?)", (self.organization_id, self.mode.value)
            )
            db.execute(f"PRAGMA application_id={APPLICATION_ID}")
            db.execute(f"PRAGMA user_version={SCHEMA_VERSION}")

    @staticmethod
    def _retain(db: sqlite3.Connection, tables: tuple[str, ...]) -> None:
        for table in tables:
            for event in ("UPDATE", "DELETE"):
                db.execute(
                    f"CREATE TRIGGER retain_{table}_{event} BEFORE {event} ON {table} "
                    "BEGIN SELECT RAISE(ABORT,'immutable ledger record'); END"
                )

    @staticmethod
    def _check_application(
        db: sqlite3.Connection, *, allow_empty: bool = False, allow_legacy: bool = False
    ) -> None:
        application = db.execute("PRAGMA application_id").fetchone()[0]
        version = db.execute("PRAGMA user_version").fetchone()[0]
        if (application, version) == (APPLICATION_ID, SCHEMA_VERSION):
            return
        if allow_legacy and (application, version) == (APPLICATION_ID, 1):
            return
        if (
            allow_empty
            and application == version == 0
            and not db.execute("SELECT 1 FROM sqlite_schema LIMIT 1").fetchone()
        ):
            return
        raise LedgerFormatError("Unsupported engine ledger application or schema")

    def _check_database(self, db: sqlite3.Connection) -> None:
        self._check_application(db)
        row = db.execute(
            "SELECT organization_id,mode FROM ledger_meta WHERE singleton=1"
        ).fetchone()
        if row is None or row[0] != self.organization_id or row[1] != self.mode.value:
            raise LedgerFormatError("Ledger belongs to another organization or mode")

    def submit(
        self,
        intent: Intent,
        *,
        provider_key: str,
        idempotency: Idempotency = Idempotency.NONE,
        supported_consistency: frozenset[Consistency] = frozenset({Consistency.C0, Consistency.C1}),
        max_attempts: int = 3,
    ) -> Action:
        """Register once, or return current state for an identical immutable submission."""
        if type(intent) is not Intent or intent.organization_id != self.organization_id:
            raise ValidationError("Intent must belong to the ledger organization")
        candidate = Action(
            intent,
            provider_key,
            idempotency=idempotency,
            supported_consistency=supported_consistency,
            max_attempts=max_attempts,
            authorized=self.mode is LedgerMode.REFERENCE,
            evidence_valid=self.mode is LedgerMode.REFERENCE,
        )
        if max_attempts > 64:
            raise ValidationError("This ledger profile supports at most 64 attempts")
        profile = canonical_bytes(sorted(c.value for c in supported_consistency))
        binding = (
            intent.canonical,
            intent.intent_digest,
            intent.account,
            provider_key,
            idempotency.value,
            profile,
            max_attempts,
        )
        with self._transaction(write=True) as db:
            previous = db.execute(
                "SELECT * FROM operations WHERE operation_id=?", (intent.operation_id,)
            ).fetchone()
            if previous is not None:
                stored = tuple(
                    previous[name]
                    for name in (
                        "intent",
                        "intent_digest",
                        "account",
                        "provider_key",
                        "idempotency",
                        "supported_consistency",
                        "max_attempts",
                    )
                )
                if stored != binding:
                    raise LedgerConflict("Operation identity has another immutable binding")
                return self._load(db, intent.operation_id)
            reservation = db.execute(
                "SELECT operation_id FROM reservations WHERE namespace=? AND business_key=?",
                (intent.business_effect_namespace, intent.business_effect_key),
            ).fetchone()
            if reservation is not None:
                raise LedgerConflict("Business effect is permanently reserved by another operation")
            if db.execute(
                "SELECT 1 FROM operations WHERE account=? AND provider_key=?",
                (intent.account, provider_key),
            ).fetchone():
                raise LedgerConflict("Provider key is already bound in this account")
            db.execute(
                "INSERT INTO operations VALUES (?,?,?,?,?,?,?,?)", (intent.operation_id, *binding)
            )
            db.execute(
                "INSERT INTO reservations VALUES (?,?,?)",
                (
                    intent.business_effect_namespace,
                    intent.business_effect_key,
                    intent.operation_id,
                ),
            )
            db.execute(
                "INSERT INTO action_state VALUES (?,?,?,?,?,?,?,?)",
                (
                    intent.operation_id,
                    0,
                    0,
                    int(candidate.authorized),
                    int(candidate.evidence_valid),
                    candidate.disposition.value,
                    candidate.effect.value,
                    candidate.reconciliation.value,
                ),
            )
            self._journal(db, candidate, "submit", None, canonical_bytes({}))
            return candidate

    def get(self, operation_id: str) -> Action:
        text(operation_id, "operation_id")
        with self._transaction() as db:
            return self._load(db, operation_id)

    def reservation(self, namespace: str, business_key: str) -> str | None:
        text(namespace, "namespace")
        text(business_key, "business_key")
        with self._transaction() as db:
            row = db.execute(
                "SELECT operation_id FROM reservations WHERE namespace=? AND business_key=?",
                (namespace, business_key),
            ).fetchone()
            return row[0] if row else None

    @staticmethod
    def _load(db: sqlite3.Connection, operation_id: str) -> Action:
        binding = db.execute(
            "SELECT * FROM operations WHERE operation_id=?", (operation_id,)
        ).fetchone()
        if binding is None:
            raise OperationNotFound(operation_id)
        intent = Intent.from_json(binding["intent"])
        if intent.intent_digest != binding["intent_digest"] or intent.operation_id != operation_id:
            raise LedgerFormatError("Stored intent identity or digest mismatch")
        state = db.execute(
            "SELECT * FROM action_state WHERE operation_id=?", (operation_id,)
        ).fetchone()
        attempts = tuple(
            Attempt(
                row["attempt_id"],
                row["generation"],
                Phase(row["phase"]),
                Effect(row["assessment"]),
                frozenset(parse_json(row["repetition_covered"])),
            )
            for row in db.execute(
                "SELECT * FROM attempts WHERE operation_id=? ORDER BY ordinal",
                (operation_id,),
            )
        )
        observations = tuple(
            Observation(
                row["observation_id"],
                row["attempt_id"],
                row["intent_digest"],
                Effect(row["assessment"]),
                row["provider_effect_id"],
            )
            for row in db.execute(
                "SELECT * FROM observations WHERE operation_id=? ORDER BY ordinal",
                (operation_id,),
            )
        )
        return Action(
            intent=intent,
            provider_key=binding["provider_key"],
            idempotency=Idempotency(binding["idempotency"]),
            supported_consistency=frozenset(
                Consistency(c) for c in parse_json(binding["supported_consistency"])
            ),
            max_attempts=binding["max_attempts"],
            version=state["version"],
            generation=state["generation"],
            authorized=bool(state["authorized"]),
            evidence_valid=bool(state["evidence_valid"]),
            disposition=Disposition(state["disposition"]),
            effect=Effect(state["effect"]),
            reconciliation=Reconciliation(state["reconciliation"]),
            attempts=attempts,
            observations=observations,
        )

    def apply(
        self,
        operation_id: str,
        *,
        expected_version: int,
        command: Command,
        **arguments,
    ) -> Action:
        """Commit a trusted model command. SEND_POSSIBLE grants no transport authority."""
        if self.mode is LedgerMode.GOVERNED:
            raise TransitionError("Governed commands require the authority controller")
        text(operation_id, "operation_id")
        integer(expected_version, "expected_version")
        if type(command) is not Command:
            raise ValidationError("Use a supported typed ledger command")
        data = _command_data(arguments)
        with self._transaction(write=True) as db:
            before = self._load(db, operation_id)
            if before.version != expected_version:
                raise TransitionError("Stale authoritative state version")
            methods = {
                Command.EVALUATE: Action.evaluate,
                Command.SET_AUTHORITY: Action.set_authority,
                Command.ADMIT: Action.admit,
                Command.SEND_POSSIBLE: Action.cross_send_boundary,
                Command.STOP: Action.stop,
                Command.TAKEOVER: Action.takeover,
                Command.OBSERVE: Action.observe,
                Command.BEGIN_RECONCILIATION: Action.begin_reconciliation,
            }
            if command in (Command.ADMIT, Command.SEND_POSSIBLE, Command.OBSERVE):
                arguments = {**arguments, "expected_version": expected_version}
            after = methods[command](before, **arguments)
            if after is before:  # An exact duplicate observation is a durable no-op.
                return before
            integer(after.version, "version")
            integer(after.generation, "generation")
            self._store_change(db, before, after)
            self._journal(db, after, command.value, before.version, data)
            return after

    @staticmethod
    def _store_change(db: sqlite3.Connection, before: Action, after: Action) -> None:
        operation_id = after.intent.operation_id
        changed = db.execute(
            "UPDATE action_state SET version=?,generation=?,authorized=?,evidence_valid=?,"
            "disposition=?,effect=?,reconciliation=? WHERE operation_id=? AND version=?",
            (
                after.version,
                after.generation,
                int(after.authorized),
                int(after.evidence_valid),
                after.disposition.value,
                after.effect.value,
                after.reconciliation.value,
                operation_id,
                before.version,
            ),
        )
        if changed.rowcount != 1:
            raise TransitionError("Stale authoritative state version")
        for ordinal, attempt in enumerate(after.attempts):
            if ordinal < len(before.attempts):
                if attempt != before.attempts[ordinal]:
                    db.execute(
                        "UPDATE attempts SET phase=?,assessment=? "
                        "WHERE operation_id=? AND attempt_id=?",
                        (
                            attempt.phase.value,
                            attempt.assessment.value,
                            operation_id,
                            attempt.attempt_id,
                        ),
                    )
            else:
                db.execute(
                    "INSERT INTO attempts VALUES (?,?,?,?,?,?,?)",
                    (
                        operation_id,
                        ordinal,
                        attempt.attempt_id,
                        attempt.generation,
                        canonical_bytes(sorted(attempt.repetition_covered)),
                        attempt.phase.value,
                        attempt.assessment.value,
                    ),
                )
        for ordinal in range(len(before.observations), len(after.observations)):
            observation = after.observations[ordinal]
            db.execute(
                "INSERT INTO observations VALUES (?,?,?,?,?,?,?)",
                (
                    operation_id,
                    ordinal,
                    observation.observation_id,
                    observation.attempt_id,
                    observation.intent_digest,
                    observation.assessment.value,
                    observation.provider_effect_id,
                ),
            )

    @staticmethod
    def _journal(
        db: sqlite3.Connection,
        action: Action,
        command: str,
        previous_version: int | None,
        data: bytes,
    ) -> None:
        db.execute(
            "INSERT INTO journal(operation_id,command,previous_version,version,generation,"
            "disposition,effect,reconciliation,data) VALUES (?,?,?,?,?,?,?,?,?)",
            (
                action.intent.operation_id,
                command,
                previous_version,
                action.version,
                action.generation,
                action.disposition.value,
                action.effect.value,
                action.reconciliation.value,
                data,
            ),
        )

    def history(self, operation_id: str) -> tuple[JournalEntry, ...]:
        text(operation_id, "operation_id")
        with self._transaction() as db:
            if (
                db.execute(
                    "SELECT 1 FROM operations WHERE operation_id=?", (operation_id,)
                ).fetchone()
                is None
            ):
                raise OperationNotFound(operation_id)
            return tuple(
                JournalEntry(
                    row["sequence"],
                    operation_id,
                    row["command"],
                    row["previous_version"],
                    row["version"],
                    row["generation"],
                    Disposition(row["disposition"]),
                    Effect(row["effect"]),
                    Reconciliation(row["reconciliation"]),
                    row["data"],
                )
                for row in db.execute(
                    "SELECT * FROM journal WHERE operation_id=? ORDER BY sequence",
                    (operation_id,),
                )
            )
