"""Governed dispatch and reconciliation for the built-in synthetic protocol."""

from dataclasses import replace
from urllib.parse import urlencode
from uuid import uuid4

from . import synthetic, transport
from .authority import Authority, AuthorizationDenied
from .canonical import ValidationError, canonical_bytes, closed_object, parse_json, text
from .ledger import LedgerConflict
from .model import Action, Disposition, Effect, Idempotency, Phase, RepetitionProof, TransitionError
from .synthetic import Profile, Request
from .transport import Endpoint, Reply


class Engine:
    def __init__(
        self, authority: Authority, *, endpoint: Endpoint | None = None, account: str | None = None
    ):
        self.authority = authority
        self.ledger = authority.ledger
        binding = self.configuration(authority)
        if binding is None:
            if type(endpoint) is not Endpoint or account is None:
                raise ValidationError("Initial connector setup requires endpoint and account")
            text(account, "account")
            profile = Profile.from_reply(transport.read(endpoint, "/v1/profile"))
            binding = {
                "host": endpoint.host,
                "port": endpoint.port,
                "account": account,
                "profile": profile.value,
                "adapter_digest": synthetic.ADAPTER_DIGEST,
            }
            with self.ledger._transaction(write=True) as db:
                previous = db.execute("SELECT binding FROM connector WHERE singleton=1").fetchone()
                if previous is None:
                    db.execute("INSERT INTO connector VALUES (1,?)", (canonical_bytes(binding),))
                elif previous[0] != canonical_bytes(binding):
                    raise LedgerConflict("Connector binding already exists")
        closed_object(binding, {"host", "port", "account", "profile", "adapter_digest"})
        self.endpoint = Endpoint(binding["port"], binding["host"])
        self.account = binding["account"]
        self.profile = Profile.from_reply(
            Reply(200, canonical_bytes(binding["profile"]), binding["profile"]["provider_id"])
        )
        self._artifact = binding["adapter_digest"]
        if (endpoint is not None and endpoint != self.endpoint) or (
            account is not None and account != self.account
        ):
            raise LedgerConflict("Cannot replace a persisted connector binding")

    @staticmethod
    def configuration(authority: Authority) -> dict | None:
        with authority.ledger._transaction() as db:
            row = db.execute("SELECT binding FROM connector WHERE singleton=1").fetchone()
            return parse_json(row[0]) if row else None

    def _live(self):
        observed = Profile.from_reply(transport.read(self.endpoint, "/v1/profile"))
        if observed != self.profile or self._artifact != synthetic.ADAPTER_DIGEST:
            raise LedgerConflict("Provider identity, contract, or adapter artifact changed")

    def _validate(self, request: Request, action: Action, attempt_id: str | None = None):
        if action.intent.account != self.account:
            raise ValidationError("Operation belongs to another connector account")
        synthetic.validate(request, action, self.endpoint, self.profile, attempt_id)

    def prepare(self, operation_id: str) -> Action:
        before = self.ledger.get(operation_id)
        self._live()
        request = synthetic.build(before, self.endpoint, self.profile)
        self._validate(request, before)
        with self.authority._write() as (db, now):
            current = self.ledger._load(db, operation_id)
            previous = db.execute(
                "SELECT request FROM prepared_requests WHERE operation_id=?", (operation_id,)
            ).fetchone()
            if previous is not None:
                if previous[0] != request.canonical:
                    raise LedgerConflict("Prepared request cannot be replaced")
                return current
            if current.disposition is Disposition.CLOSED:
                raise TransitionError("Closed operation cannot acquire a dispatch binding")
            db.execute(
                "INSERT INTO prepared_requests VALUES (?,?,?)",
                (operation_id, request.canonical, request.digest),
            )
            after = current._change()
            self.authority._save(
                db, current, after, "request_prepared", {"digest": request.digest, "at": now}
            )
        return after

    def _prepared(self, db, action: Action) -> Request:
        row = db.execute(
            "SELECT request,digest FROM prepared_requests WHERE operation_id=?",
            (action.intent.operation_id,),
        ).fetchone()
        if row is None:
            raise TransitionError("Prepare the request before approval and dispatch")
        request = Request.from_json(row[0])
        self._validate(request, action)
        if request.digest != row[1]:
            raise ValidationError("Stored prepared-request digest mismatch")
        return request

    def _past_requests(self, db, action: Action):
        for attempt in action.attempts:
            if attempt.phase is not Phase.POSSIBLY_SENT:
                continue
            row = db.execute(
                "SELECT request,digest FROM dispatch_requests "
                "WHERE operation_id=? AND attempt_id=?",
                (action.intent.operation_id, attempt.attempt_id),
            ).fetchone()
            if row is None:
                raise ValidationError(
                    "Unbound previous attempt cannot support evidence or repetition"
                )
            request = Request.from_json(row[0])
            self._validate(request, action, attempt.attempt_id)
            if row[1] != request.digest:
                raise ValidationError("Stored attempt-request digest mismatch")

    def dispatch(self, operation_id: str, *, actor: str, repeat: bool = False) -> Action:
        text(actor, "actor")
        if type(repeat) is not bool:
            raise ValidationError("Repeat must be an explicit boolean")
        before = self.ledger.get(operation_id)
        if before.disposition is Disposition.CLOSED:
            if before.effect is Effect.CONFIRMED:
                return before
            raise TransitionError("Closed operations cannot dispatch")
        self._live()
        if repeat:
            before = self.recover(operation_id, actor=actor)
        attempt_id = "attempt-" + uuid4().hex
        with self.authority._write() as (db, now):
            current, _, grant = self.authority._checked(db, operation_id, before.version, now)
            prepared = self._prepared(db, current)
            if grant["request_digest"] != prepared.digest:
                raise AuthorizationDenied("Approval must bind the prepared request")
            proof = None
            unresolved = any(
                a.phase is Phase.POSSIBLY_SENT and a.assessment is not Effect.NO_EFFECT
                for a in current.attempts
            )
            if repeat and unresolved:
                if self.profile.idempotency is not Idempotency.PERMANENT:
                    raise TransitionError("Uncertain repetition requires a permanent-key contract")
                self._past_requests(db, current)
                proof = RepetitionProof(
                    current.intent.intent_digest,
                    frozenset(
                        a.attempt_id for a in current.attempts if a.phase is Phase.POSSIBLY_SENT
                    ),
                    current.intent.account,
                    current.intent.capability,
                    current.provider_key,
                )
            concrete = replace(
                prepared, headers=(*prepared.headers, ("X-WS-Attempt-ID", attempt_id))
            )
            self._validate(concrete, current, attempt_id)
            admitted = current.admit(
                attempt_id,
                expected_version=current.version,
                generation=current.generation,
                proof=proof,
            )
            self.authority._save(
                db,
                current,
                admitted,
                "dispatch_admitted",
                {
                    "attempt_id": attempt_id,
                    "request_digest": concrete.digest,
                    "approval_id": grant["approval_id"],
                    "at": now,
                    "repetition_covered": sorted(proof.covered_attempt_ids) if proof else [],
                },
            )
            db.execute(
                "INSERT INTO dispatch_requests VALUES (?,?,?,?,?)",
                (
                    operation_id,
                    attempt_id,
                    concrete.canonical,
                    concrete.digest,
                    grant["approval_id"],
                ),
            )
        self._release(admitted, concrete)
        # Only this call's acknowledged boundary permits this single transport invocation.
        reply = self._transmit(concrete)
        return self._receive(operation_id, reply, actor=actor, attempt_id=attempt_id)

    def _release(self, admitted: Action, request: Request):
        operation_id = admitted.intent.operation_id
        attempt_id = admitted.attempts[-1].attempt_id
        with self.authority._write() as (db, now):
            snapshot = self.ledger._load(db, operation_id)
            current, _, grant = self.authority._checked(db, operation_id, snapshot.version, now)
            prepared = self._prepared(db, current)
            row = db.execute(
                "SELECT request,digest,approval_id FROM dispatch_requests "
                "WHERE operation_id=? AND attempt_id=?",
                (operation_id, attempt_id),
            ).fetchone()
            self._validate(request, current, attempt_id)
            if (
                row is None
                or row[0] != request.canonical
                or row[1] != request.digest
                or row[2] != grant["approval_id"]
                or grant["request_digest"] != prepared.digest
            ):
                raise AuthorizationDenied("Dispatch binding or approved request changed")
            after = current.cross_send_boundary(
                attempt_id, expected_version=current.version, generation=admitted.generation
            )
            self.authority._save(
                db,
                current,
                after,
                "send_possible",
                {
                    "attempt_id": attempt_id,
                    "request_digest": request.digest,
                    "at": now,
                },
            )

    @staticmethod
    def _transmit(request: Request) -> Reply:
        return transport.exchange(
            request.endpoint, request.method, request.path, request.headers, request.body
        )

    def _read_permission(self, db, action: Action, actor: str, now: int):
        self.authority._read_permission(
            db,
            actor=actor,
            account=action.intent.account,
            capability=action.intent.capability,
            resource=action.intent.resource,
            now=now,
        )

    def reconcile(self, operation_id: str, *, actor: str) -> Action:
        with self.authority._write() as (db, now):
            before = self.ledger._load(db, operation_id)
            self._read_permission(db, before, actor, now)
            if not any(a.phase is Phase.POSSIBLY_SENT for a in before.attempts):
                raise TransitionError("No possibly sent attempt to reconcile")
        self._live()
        path = "/v1/effects?" + urlencode(
            {"account": before.intent.account, "operation_id": operation_id}
        )
        reply = transport.read(self.endpoint, path, self.profile.provider_id)
        return self._receive(operation_id, reply, actor=actor, attempt_id=None)

    def _receive(
        self, operation_id: str, reply: Reply, *, actor: str, attempt_id: str | None
    ) -> Action:
        with self.authority._write() as (db, now):
            before = self.ledger._load(db, operation_id)
            error = None
            try:
                self._read_permission(db, before, actor, now)
                prepared = self._prepared(db, before)
                self._past_requests(db, before)
                facts = synthetic.observations(
                    reply, before, self.profile, prepared, attempt_id=attempt_id
                )
            except (ValidationError, AuthorizationDenied) as failure:
                error = (
                    "read_permission_denied"
                    if isinstance(failure, AuthorizationDenied)
                    else "unverified_response"
                )
                facts = ()
            after = before
            for fact in facts:
                after = after.observe(fact, expected_version=after.version)
            if after is before:
                after = (
                    before.takeover()
                    if (
                        before.disposition is Disposition.ADMITTED
                        and before.attempts[-1].phase is Phase.POSSIBLY_SENT
                    )
                    else before._change()
                )
            response_id = uuid4().hex
            db.execute(
                "INSERT INTO provider_responses VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    response_id,
                    operation_id,
                    "post" if attempt_id else "lookup",
                    attempt_id,
                    reply.status,
                    reply.body,
                    int(error is None),
                    error,
                    now,
                ),
            )
            self.authority._save(
                db,
                before,
                after,
                "provider_response",
                {
                    "response_id": response_id,
                    "actor": actor,
                    "admitted": error is None,
                    "error": error or reply.error,
                    "at": now,
                },
            )
        return after

    def inventory(self, resource: str, *, actor: str) -> dict:
        text(resource, "resource")
        with self.authority._write() as (db, now):
            self.authority._read_permission(
                db,
                actor=actor,
                account=self.account,
                capability="sim.effect.create",
                resource=resource,
                now=now,
            )
        self._live()
        reply = transport.read(
            self.endpoint,
            "/v1/resources?" + urlencode({"account": self.account, "resource": resource}),
            self.profile.provider_id,
        )
        value = synthetic.stock(reply, self.profile, account=self.account, resource=resource)
        with self.authority._write() as (db, now):
            self.authority._read_permission(
                db,
                actor=actor,
                account=self.account,
                capability="sim.effect.create",
                resource=resource,
                now=now,
            )
        return value

    def recover(self, operation_id: str, *, actor: str) -> Action:
        return self._stop(operation_id, actor=actor, close=False)

    def cancel(self, operation_id: str, *, actor: str) -> Action:
        return self._stop(operation_id, actor=actor, close=True)

    def _stop(self, operation_id: str, *, actor: str, close: bool) -> Action:
        with self.authority._write() as (db, now):
            self.authority._admin(actor)
            before = self.ledger._load(db, operation_id)
            if close and before.disposition is Disposition.CLOSED:
                return before
            after = before.stop(close=True) if close else before.takeover()
            self.authority._save(
                db, before, after, "cancel" if close else "recover", {"actor": actor, "at": now}
            )
        return after

    def inspect(self, operation_id: str) -> dict:
        with self.ledger._transaction() as db:
            action = self.ledger._load(db, operation_id)
            approvals = [
                dict(row)
                for row in db.execute(
                    "SELECT a.*,r.at AS revoked_at FROM approvals a LEFT JOIN revocations r "
                    "ON r.approval_id=a.approval_id WHERE operation_id=? ORDER BY sequence",
                    (operation_id,),
                )
            ]
            responses = [
                {**dict(row), "body": row["body"].decode("utf-8", errors="replace")}
                for row in db.execute(
                    "SELECT * FROM provider_responses WHERE operation_id=? ORDER BY rowid",
                    (operation_id,),
                )
            ]
            prepared = db.execute(
                "SELECT request,digest FROM prepared_requests WHERE operation_id=?", (operation_id,)
            ).fetchone()
            history = [
                {
                    "sequence": row["sequence"],
                    "command": row["command"],
                    "version": row["version"],
                    "previous_version": row["previous_version"],
                    "data": parse_json(row["data"]),
                }
                for row in db.execute(
                    "SELECT * FROM journal WHERE operation_id=? ORDER BY sequence", (operation_id,)
                )
            ]
        return {
            "intent": action.intent.as_object(),
            "disposition": action.disposition.value,
            "effect": action.effect.value,
            "reconciliation": action.reconciliation.value,
            "version": action.version,
            "generation": action.generation,
            "approvals": approvals,
            "prepared_request": {"digest": prepared[1], "request": parse_json(prepared[0])}
            if prepared
            else None,
            "attempts": [
                {
                    "attempt_id": a.attempt_id,
                    "phase": a.phase.value,
                    "assessment": a.assessment.value,
                    "generation": a.generation,
                    "repetition_covered": sorted(a.repetition_covered),
                }
                for a in action.attempts
            ],
            "observations": [
                {
                    "observation_id": o.observation_id,
                    "attempt_id": o.attempt_id,
                    "assessment": o.assessment.value,
                    "provider_effect_id": o.provider_effect_id,
                }
                for o in action.observations
            ],
            "responses": responses,
            "history": history,
        }
