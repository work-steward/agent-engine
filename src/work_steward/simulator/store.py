"""Provider-side transactions and explicitly out-of-band test-harness controls."""

import hashlib
import sqlite3
from contextlib import contextmanager
from enum import StrEnum
from pathlib import Path

from ..canonical import ValidationError, canonical_bytes, closed_object, integer, text
from ..model import Idempotency


class Behavior(StrEnum):
    APPLY = "apply"
    PENDING = "pending"
    REJECT = "reject"
    DROP_AFTER_APPLY = "drop_after_apply"
    CONTRADICTORY_STATUS = "contradictory_status"
    DUPLICATE_STATUS = "duplicate_status"


class ProviderConflict(ValueError):
    """The provider key or provider configuration conflicts with existing state."""


def request_body(value: object) -> dict:
    body = closed_object(
        value, {"operation_id", "account", "resource", "quantity", "resource_version"}
    )
    for name in ("operation_id", "account", "resource"):
        text(body[name], name)
    integer(body["quantity"], "quantity", minimum=1)
    if body["resource_version"] is not None:
        integer(body["resource_version"], "resource_version")
    return body


class ProviderStore:
    def __init__(
        self,
        path: Path,
        *,
        idempotency: Idempotency = Idempotency.PERMANENT,
        behavior: Behavior = Behavior.APPLY,
        retention_ticks: int = 10,
    ):
        self.path = Path(path)
        if type(idempotency) is not Idempotency or type(behavior) is not Behavior:
            raise ValidationError("Unsupported provider profile")
        integer(retention_ticks, "retention_ticks", minimum=1)
        self.idempotency, self.behavior, self.retention_ticks = (
            idempotency,
            behavior,
            retention_ticks,
        )
        with self.connection(write=True) as db:
            # DDL is executed individually: executescript would implicitly end the transaction.
            for sql in (
                "CREATE TABLE IF NOT EXISTS config (id INTEGER PRIMARY KEY CHECK(id=1), "
                "profile TEXT NOT NULL, behavior TEXT NOT NULL, retention INTEGER NOT NULL, "
                "tick INTEGER NOT NULL) STRICT",
                "CREATE TABLE IF NOT EXISTS resources (account TEXT NOT NULL, "
                "resource TEXT NOT NULL, "
                "quantity INTEGER NOT NULL, version INTEGER NOT NULL, "
                "PRIMARY KEY(account,resource)) STRICT",
                "CREATE TABLE IF NOT EXISTS effects (id INTEGER PRIMARY KEY, "
                "operation_id TEXT NOT NULL, "
                "attempt_id TEXT NOT NULL, account TEXT NOT NULL, resource TEXT NOT NULL, "
                "quantity INTEGER NOT NULL, resource_version INTEGER, "
                "request_digest TEXT NOT NULL, "
                "outcome TEXT NOT NULL CHECK(outcome IN ('pending','effect_confirmed',"
                "'no_effect_confirmed'))) STRICT",
                "CREATE TABLE IF NOT EXISTS dedup (account TEXT NOT NULL, "
                "provider_key TEXT NOT NULL, "
                "request_digest TEXT NOT NULL, effect_id INTEGER NOT NULL REFERENCES effects(id), "
                "expires_at INTEGER, PRIMARY KEY(account,provider_key)) STRICT",
            ):
                db.execute(sql)
            config = db.execute("SELECT * FROM config WHERE id=1").fetchone()
            if config is None:
                db.execute(
                    "INSERT INTO config VALUES (1,?,?,?,0)",
                    (idempotency.value, behavior.value, retention_ticks),
                )
            elif (config["profile"], config["behavior"], config["retention"]) != (
                idempotency.value,
                behavior.value,
                retention_ticks,
            ):
                raise ProviderConflict("Cannot change a persisted provider profile on restart")

    @contextmanager
    def connection(self, *, write: bool = False):
        if sqlite3.sqlite_version_info < (3, 37, 0):
            raise RuntimeError("SQLite 3.37 or later is required")
        db = sqlite3.connect(self.path, isolation_level=None, timeout=2.0)
        db.row_factory = sqlite3.Row
        try:
            db.execute("PRAGMA foreign_keys=ON")
            mode = db.execute("PRAGMA journal_mode=WAL").fetchone()[0]
            db.execute("PRAGMA synchronous=FULL")
            if mode != "wal" or db.execute("PRAGMA synchronous").fetchone()[0] != 2:
                raise RuntimeError("Required provider durability settings unavailable")
            if db.execute("PRAGMA foreign_keys").fetchone()[0] != 1:
                raise RuntimeError("Foreign key enforcement unavailable")
            db.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def _record(row: sqlite3.Row) -> dict:
        return {
            "provider_effect_id": f"effect-{row['id']}",
            **{
                name: row[name]
                for name in (
                    "operation_id",
                    "attempt_id",
                    "account",
                    "resource",
                    "quantity",
                    "resource_version",
                    "request_digest",
                    "outcome",
                )
            },
        }

    @staticmethod
    def _apply(db: sqlite3.Connection, body: dict) -> str:
        row = db.execute(
            "SELECT quantity,version FROM resources WHERE account=? AND resource=?",
            (body["account"], body["resource"]),
        ).fetchone()
        quantity, version = (row["quantity"], row["version"]) if row else (0, 0)
        if body["resource_version"] is not None and body["resource_version"] != version:
            return "no_effect_confirmed"
        new_quantity = quantity + body["quantity"]
        try:
            integer(new_quantity, "resulting quantity")
            integer(version + 1, "resulting resource version")
        except ValidationError:
            return "no_effect_confirmed"
        db.execute(
            "INSERT INTO resources VALUES (?,?,?,?) ON CONFLICT(account,resource) "
            "DO UPDATE SET quantity=excluded.quantity,version=excluded.version",
            (body["account"], body["resource"], new_quantity, version + 1),
        )
        return "effect_confirmed"

    def submit(self, value: object, *, attempt_id: str, provider_key: str | None) -> dict:
        body = request_body(value)
        text(attempt_id, "attempt_id")
        if self.idempotency is Idempotency.NONE:
            if provider_key is not None:
                raise ValidationError("This provider profile does not accept idempotency keys")
        else:
            text(provider_key, "provider_key")
        body_digest = hashlib.sha256(canonical_bytes(body)).hexdigest()
        with self.connection(write=True) as db:
            tick = db.execute("SELECT tick FROM config WHERE id=1").fetchone()[0]
            if provider_key is not None:
                previous = db.execute(
                    "SELECT * FROM dedup WHERE account=? AND provider_key=?",
                    (body["account"], provider_key),
                ).fetchone()
                if previous is not None and (
                    previous["expires_at"] is None or tick < previous["expires_at"]
                ):
                    if previous["request_digest"] != body_digest:
                        raise ProviderConflict("Idempotency key parameter mismatch")
                    row = db.execute(
                        "SELECT * FROM effects WHERE id=?", (previous["effect_id"],)
                    ).fetchone()
                    return self._record(row)
            if self.behavior is Behavior.PENDING:
                outcome = "pending"
            elif self.behavior is Behavior.REJECT:
                outcome = "no_effect_confirmed"
            else:
                outcome = self._apply(db, body)
            cursor = db.execute(
                "INSERT INTO effects(operation_id,attempt_id,account,resource,quantity,"
                "resource_version,request_digest,outcome) VALUES (?,?,?,?,?,?,?,?)",
                (
                    body["operation_id"],
                    attempt_id,
                    body["account"],
                    body["resource"],
                    body["quantity"],
                    body["resource_version"],
                    body_digest,
                    outcome,
                ),
            )
            effect_id = cursor.lastrowid
            if provider_key is not None:
                expires = (
                    tick + self.retention_ticks if self.idempotency is Idempotency.FINITE else None
                )
                if expires is not None:
                    integer(expires, "idempotency expiry")
                db.execute(
                    "INSERT INTO dedup VALUES (?,?,?,?,?) ON CONFLICT(account,provider_key) "
                    "DO UPDATE SET request_digest=excluded.request_digest,"
                    "effect_id=excluded.effect_id,expires_at=excluded.expires_at",
                    (body["account"], provider_key, body_digest, effect_id, expires),
                )
            row = db.execute("SELECT * FROM effects WHERE id=?", (effect_id,)).fetchone()
            return self._record(row)

    def lookup(self, *, account: str, operation_id: str) -> dict:
        text(account, "account")
        text(operation_id, "operation_id")
        with self.connection() as db:
            records = [
                self._record(row)
                for row in db.execute(
                    "SELECT * FROM effects WHERE account=? AND operation_id=? ORDER BY id LIMIT 17",
                    (account, operation_id),
                )
            ]
        truncated = len(records) > 16
        records = records[:16]
        if self.behavior is Behavior.CONTRADICTORY_STATUS:
            records = [
                {**r, "outcome": "no_effect_confirmed"} if r["outcome"] == "effect_confirmed" else r
                for r in records
            ]
        if self.behavior is Behavior.DUPLICATE_STATUS:
            records = records + records
        return {
            "account": account,
            "operation_id": operation_id,
            "records": records,
            "final_absence": False,
            "truncated": truncated,
        }

    def advance_clock(self, ticks: int) -> None:
        """Test harness control. Deliberately not exposed by the HTTP protocol."""
        integer(ticks, "ticks")
        with self.connection(write=True) as db:
            tick = db.execute("SELECT tick FROM config WHERE id=1").fetchone()[0]
            integer(tick + ticks, "new tick")
            db.execute("UPDATE config SET tick=? WHERE id=1", (tick + ticks,))

    def complete_pending(self) -> None:
        """Harness-only release of pending requests, including atomic C2 evaluation."""
        with self.connection(write=True) as db:
            pending = db.execute(
                "SELECT * FROM effects WHERE outcome='pending' ORDER BY id"
            ).fetchall()
            for row in pending:
                outcome = self._apply(db, dict(row))
                db.execute("UPDATE effects SET outcome=? WHERE id=?", (outcome, row["id"]))
