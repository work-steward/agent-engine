"""Built-in synthetic adapter and independent material/evidence validation."""

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from . import transport
from .canonical import ValidationError, canonical_bytes, closed_object, digest, integer, parse_json
from .intent import Consistency
from .model import Action, Effect, Idempotency, Observation, Phase
from .transport import Endpoint, Reply

ADAPTER_ID = "synthetic.effect.v1"
ADAPTER_DIGEST = hashlib.sha256(
    Path(__file__).read_bytes() + Path(transport.__file__).read_bytes()
).hexdigest()
SUPPORTED_CONSISTENCY = frozenset({Consistency.C0, Consistency.C1, Consistency.C2})


@dataclass(frozen=True)
class Profile:
    provider_id: str
    idempotency: Idempotency
    retention_ticks: int | None = None

    @property
    def value(self) -> dict:
        return {
            "protocol": "work-steward-synthetic/2",
            "provider_id": self.provider_id,
            "idempotency": self.idempotency.value,
            "retention_ticks": self.retention_ticks,
            "key_scope": "account",
            "parameter_match": "canonical-body",
            "atomic_resource_version": True,
            "identity_condition": True,
            "lookup_final_absence": False,
        }

    @classmethod
    def from_reply(cls, reply: Reply) -> "Profile":
        value = response_object(reply)
        closed_object(
            value,
            {
                "protocol",
                "provider_id",
                "idempotency",
                "retention_ticks",
                "key_scope",
                "parameter_match",
                "atomic_resource_version",
                "identity_condition",
                "lookup_final_absence",
            },
        )
        try:
            kind = Idempotency(value["idempotency"])
        except ValueError as error:
            raise ValidationError("Unsupported idempotency contract") from error
        provider_id = value["provider_id"]
        if type(provider_id) is not str or not re.fullmatch("[0-9a-f]{32}", provider_id):
            raise ValidationError("Invalid provider identity")
        if kind is Idempotency.FINITE:
            integer(value["retention_ticks"], "retention_ticks", minimum=1)
        result = cls(provider_id, kind, value["retention_ticks"])
        if (
            value != result.value
            or reply.provider_id != provider_id
            or (kind is not Idempotency.FINITE and result.retention_ticks is not None)
            or value["atomic_resource_version"] is not True
            or value["identity_condition"] is not True
            or value["lookup_final_absence"] is not False
        ):
            raise ValidationError("Unsupported synthetic provider contract")
        return result


def response_object(reply: Reply, provider_id: str | None = None) -> dict:
    if (
        reply.error
        or reply.status != 200
        or (provider_id is not None and reply.provider_id != provider_id)
    ):
        raise ValidationError("Unusable provider response")
    value = parse_json(reply.body)
    if type(value) is not dict:
        raise ValidationError("Provider response must be an object")
    return value


def wire_identifier(value: str):
    if type(value) is not str or not re.fullmatch("[A-Za-z0-9._:-]{1,128}", value):
        raise ValidationError("Wire identifiers must use bounded ASCII tokens")


@dataclass(frozen=True)
class Request:
    endpoint: Endpoint
    provider_id: str
    intent_digest: str
    method: str
    path: str
    headers: tuple[tuple[str, str], ...]
    body: bytes

    @property
    def value(self) -> dict:
        return {
            "host": self.endpoint.host,
            "port": self.endpoint.port,
            "provider_id": self.provider_id,
            "intent_digest": self.intent_digest,
            "method": self.method,
            "path": self.path,
            "headers": [list(pair) for pair in self.headers],
            "body": self.body.decode("utf-8"),
        }

    @property
    def canonical(self) -> bytes:
        return canonical_bytes(self.value)

    @property
    def digest(self) -> str:
        return digest("dispatch", self.value)

    @classmethod
    def from_json(cls, data: bytes) -> "Request":
        value = closed_object(
            parse_json(data),
            {"host", "port", "provider_id", "intent_digest", "method", "path", "headers", "body"},
        )
        if (
            type(value["body"]) is not str
            or type(value["headers"]) is not list
            or any(
                type(pair) is not list
                or len(pair) != 2
                or any(type(item) is not str for item in pair)
                for pair in value["headers"]
            )
        ):
            raise ValidationError("Malformed stored request")
        return cls(
            Endpoint(value["port"], value["host"]),
            value["provider_id"],
            value["intent_digest"],
            value["method"],
            value["path"],
            tuple(tuple(pair) for pair in value["headers"]),
            value["body"].encode("utf-8"),
        )


def build(action: Action, endpoint: Endpoint, profile: Profile) -> Request:
    intent = action.intent
    body = canonical_bytes(
        {
            "operation_id": intent.operation_id,
            "account": intent.account,
            "resource": intent.resource,
            "quantity": intent.quantity,
            "resource_version": intent.resource_version,
        }
    )
    headers = (
        ("Host", f"{endpoint.host}:{endpoint.port}"),
        ("Content-Type", "application/json"),
        ("Content-Length", str(len(body))),
        ("X-WS-Provider-ID", profile.provider_id),
    )
    if profile.idempotency is not Idempotency.NONE:
        headers = (*headers, ("Idempotency-Key", action.provider_key))
    return Request(
        endpoint, profile.provider_id, intent.intent_digest, "POST", "/v1/effects", headers, body
    )


def validate(
    request: Request,
    action: Action,
    endpoint: Endpoint,
    profile: Profile,
    attempt_id: str | None = None,
):
    """Check fields against stored intent, without calling the request builder."""
    intent = action.intent
    if (
        request.endpoint != endpoint
        or request.provider_id != profile.provider_id
        or request.intent_digest != intent.intent_digest
        or request.method != "POST"
        or request.path != "/v1/effects"
        or intent.adapter_id != ADAPTER_ID
        or intent.adapter_digest != ADAPTER_DIGEST
        or intent.capability != "sim.effect.create"
        or intent.consistency not in SUPPORTED_CONSISTENCY
        or action.idempotency is not profile.idempotency
    ):
        raise ValidationError("Request destination, artifact, or capability mismatch")
    value = closed_object(
        parse_json(request.body),
        {"operation_id", "account", "resource", "quantity", "resource_version"},
    )
    if (
        any(value[name] != getattr(intent, name) for name in value)
        or type(value["quantity"]) is not int
        or (value["resource_version"] is not None and type(value["resource_version"]) is not int)
        or canonical_bytes(value) != request.body
    ):
        raise ValidationError("Request does not realize the approved intent")
    expected = {
        "Host": f"127.0.0.1:{endpoint.port}",
        "Content-Type": "application/json",
        "Content-Length": str(len(request.body)),
        "X-WS-Provider-ID": profile.provider_id,
    }
    if profile.idempotency is not Idempotency.NONE:
        wire_identifier(action.provider_key)
        expected["Idempotency-Key"] = action.provider_key
    if attempt_id is not None:
        wire_identifier(attempt_id)
        expected["X-WS-Attempt-ID"] = attempt_id
    if (
        type(request.headers) is not tuple
        or len(request.headers) != len(expected)
        or dict(request.headers) != expected
    ):
        raise ValidationError("Material request headers differ from the approved binding")


def stock(reply: Reply, profile: Profile, *, account: str, resource: str) -> dict:
    value = closed_object(
        response_object(reply, profile.provider_id), {"account", "resource", "quantity", "version"}
    )
    if value["account"] != account or value["resource"] != resource:
        raise ValidationError("Inventory response scope mismatch")
    integer(value["quantity"], "quantity")
    integer(value["version"], "version")
    return value


def observations(
    reply: Reply, action: Action, profile: Profile, prepared: Request, *, attempt_id: str | None
) -> tuple[Observation, ...]:
    value = response_object(reply, profile.provider_id)
    if attempt_id is None:
        closed_object(value, {"account", "operation_id", "records", "final_absence", "truncated"})
        if (
            value["account"] != action.intent.account
            or value["operation_id"] != action.intent.operation_id
            or value["final_absence"] is not False
            or type(value["truncated"]) is not bool
            or type(value["records"]) is not list
            or len(value["records"]) > 32
        ):
            raise ValidationError("Invalid lookup envelope")
        records = value["records"]
    else:
        records = [value]
    sent = {
        attempt.attempt_id for attempt in action.attempts if attempt.phase is Phase.POSSIBLY_SENT
    }
    results = []
    for record in records:
        closed_object(
            record,
            {
                "provider_effect_id",
                "operation_id",
                "attempt_id",
                "account",
                "resource",
                "quantity",
                "resource_version",
                "request_digest",
                "outcome",
                "provider_key",
            },
        )
        if (
            any(
                record[name] != getattr(action.intent, name)
                for name in ("operation_id", "account", "resource", "quantity", "resource_version")
            )
            or type(record["quantity"]) is not int
            or (
                record["resource_version"] is not None
                and type(record["resource_version"]) is not int
            )
            or record["request_digest"] != hashlib.sha256(prepared.body).hexdigest()
            or record["provider_key"]
            != (None if profile.idempotency is Idempotency.NONE else action.provider_key)
            or type(record["provider_effect_id"]) is not str
            or not re.fullmatch("effect-[1-9][0-9]{0,18}", record["provider_effect_id"])
            or type(record["attempt_id"]) is not str
            or record["attempt_id"] not in sent
            or type(record["outcome"]) is not str
            or record["outcome"]
            not in {Effect.PENDING.value, Effect.NO_EFFECT.value, Effect.CONFIRMED.value}
        ):
            raise ValidationError("Receipt is not evidence for this operation")
        targets = (
            sent
            if profile.idempotency is Idempotency.PERMANENT
            else {attempt_id or record["attempt_id"]}
        )
        for target in sorted(targets):
            identity = hashlib.sha256(
                b"ws-observation-1\0"
                + canonical_bytes(
                    {"provider_id": profile.provider_id, "record": record, "target": target}
                )
            ).hexdigest()
            results.append(
                Observation(
                    identity,
                    target,
                    action.intent.intent_digest,
                    Effect(record["outcome"]),
                    record["provider_effect_id"],
                )
            )
    return tuple(results)
