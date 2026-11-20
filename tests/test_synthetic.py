import hashlib
import json
from dataclasses import replace

import pytest

from work_steward import synthetic
from work_steward.canonical import ValidationError, canonical_bytes
from work_steward.intent import Consistency
from work_steward.model import Action, Idempotency
from work_steward.synthetic import ADAPTER_DIGEST, ADAPTER_ID, Profile, Request
from work_steward.transport import Endpoint, Reply


@pytest.fixture
def mapped(intent):
    action = Action(
        replace(intent, adapter_id=ADAPTER_ID, adapter_digest=ADAPTER_DIGEST),
        "key-1",
        idempotency=Idempotency.PERMANENT,
    )
    endpoint, profile = Endpoint(12345), Profile("a" * 32, Idempotency.PERMANENT)
    return action, endpoint, profile, synthetic.build(action, endpoint, profile)


def test_mapping_has_independent_golden_body_and_wire_headers(mapped):
    action, endpoint, profile, request = mapped
    assert request.body == (
        b'{"account":"account-1","operation_id":"op-1","quantity":1,'
        b'"resource":"resource-1","resource_version":null}'
    )
    assert dict(request.headers) == {
        "Host": "127.0.0.1:12345",
        "Content-Type": "application/json",
        "Content-Length": str(len(request.body)),
        "X-WS-Provider-ID": "a" * 32,
        "Idempotency-Key": "key-1",
    }
    synthetic.validate(request, action, endpoint, profile)
    assert Request.from_json(request.canonical) == request


@pytest.mark.parametrize(
    "changes",
    [
        {"method": "PUT"},
        {"path": "/v1/effects?override=true"},
        {"provider_id": "b" * 32},
        {"endpoint": Endpoint(12346)},
        {"intent_digest": "b" * 64},
        {"headers": ()},
        {"headers": (("Host", "elsewhere"),) * 5},
        {
            "body": (
                b'{"operation_id":"op-1","account":"account-1",'
                b'"resource":"resource-1","quantity":true,"resource_version":null}'
            )
        },
    ],
)
def test_validator_rejects_changed_request_semantics(mapped, changes):
    action, endpoint, profile, request = mapped
    with pytest.raises(ValidationError):
        synthetic.validate(replace(request, **changes), action, endpoint, profile)


@pytest.mark.parametrize(
    "changes",
    [
        {"adapter_id": "unapproved"},
        {"adapter_digest": "b" * 64},
        {"consistency": Consistency.C3, "resource_version": 0},
    ],
)
def test_validator_rejects_unsupported_adapter_or_consistency(mapped, changes):
    action, endpoint, profile, request = mapped
    with pytest.raises(ValidationError):
        synthetic.validate(
            request, replace(action, intent=replace(action.intent, **changes)), endpoint, profile
        )


@pytest.mark.parametrize(
    "changes", [{"body": 1}, {"headers": {}}, {"headers": [["Host"]]}, {"headers": [["Host", 1]]}]
)
def test_stored_request_schema_is_closed(mapped, changes):
    value = {**mapped[-1].value, **changes}
    with pytest.raises(ValidationError):
        Request.from_json(json.dumps(value).encode())


@pytest.mark.parametrize(
    "changes",
    [
        {"protocol": "other"},
        {"idempotency": "unknown"},
        {"provider_id": "other"},
        {"atomic_resource_version": False},
        {"identity_condition": 1},
        {"lookup_final_absence": True},
        {"retention_ticks": 10},
        {"key_scope": "request"},
    ],
)
def test_provider_contract_is_explicit_and_typed(mapped, changes):
    profile = mapped[2]
    reply = Reply(200, canonical_bytes({**profile.value, **changes}), profile.provider_id)
    with pytest.raises(ValidationError):
        Profile.from_reply(reply)


def test_finite_contract_is_parsed_but_not_promoted_to_permanent():
    profile = Profile("b" * 32, Idempotency.FINITE, 10)
    assert (
        Profile.from_reply(Reply(200, canonical_bytes(profile.value), profile.provider_id))
        == profile
    )
    with pytest.raises(ValidationError):
        Profile.from_reply(
            Reply(
                200,
                canonical_bytes({**profile.value, "retention_ticks": True}),
                profile.provider_id,
            )
        )
    with pytest.raises(ValidationError):
        synthetic.response_object(Reply(200, b"[]"))
    with pytest.raises(ValidationError):
        synthetic.wire_identifier("key\nwith-controls")


@pytest.mark.parametrize(
    "changes",
    [
        {"operation_id": "other"},
        {"account": "other"},
        {"resource": "other"},
        {"quantity": True},
        {"provider_effect_id": 1},
        {"provider_effect_id": "other"},
        {"request_digest": "other"},
        {"attempt_id": "unknown"},
        {"attempt_id": []},
        {"outcome": []},
        {"outcome": "unknown"},
        {"provider_key": "another-key"},
    ],
)
def test_receipts_cannot_rebind_material_facts(mapped, changes):
    action, _, profile, request = mapped
    action = action.evaluate().admit("a1", expected_version=1, generation=0)
    action = action.cross_send_boundary("a1", expected_version=2, generation=0)
    record = {
        **json.loads(request.body),
        "provider_effect_id": "effect-1",
        "attempt_id": "a1",
        "request_digest": hashlib.sha256(request.body).hexdigest(),
        "outcome": "effect_confirmed",
        "provider_key": "key-1",
        **changes,
    }
    with pytest.raises(ValidationError):
        synthetic.observations(
            Reply(200, canonical_bytes(record), profile.provider_id),
            action,
            profile,
            request,
            attempt_id="a1",
        )


@pytest.mark.parametrize(
    "changes",
    [
        {"account": "other"},
        {"final_absence": True},
        {"truncated": 1},
        {"records": {}},
        {"records": [{}] * 33},
    ],
)
def test_lookup_envelope_cannot_manufacture_final_absence(mapped, changes):
    action, _, profile, request = mapped
    value = {
        "account": "account-1",
        "operation_id": "op-1",
        "records": [],
        "final_absence": False,
        "truncated": False,
        **changes,
    }
    with pytest.raises(ValidationError):
        synthetic.observations(
            Reply(200, canonical_bytes(value), profile.provider_id),
            action,
            profile,
            request,
            attempt_id=None,
        )


def test_stock_scope_cannot_be_substituted(mapped):
    profile = mapped[2]
    with pytest.raises(ValidationError):
        synthetic.stock(
            Reply(
                200,
                canonical_bytes(
                    {"account": "other", "resource": "resource-1", "quantity": 0, "version": 0}
                ),
                profile.provider_id,
            ),
            profile,
            account="account-1",
            resource="resource-1",
        )
