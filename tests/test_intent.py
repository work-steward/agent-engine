import hashlib
import json
from dataclasses import FrozenInstanceError, replace

import pytest
from hypothesis import given
from hypothesis import strategies as st

from work_steward.canonical import (
    MAX_INTEGER,
    ValidationError,
    canonical_bytes,
    digest,
    parse_json,
)
from work_steward.intent import Consistency, EvidenceRef, Intent


def test_rfc8785_utf16_sorting_vector():
    # RFC 8785 section 3.2.3: UTF-16 ordering differs from Python code-point sorting.
    value = {
        "\u20ac": "Euro Sign",
        "\r": "Carriage Return",
        "\ufb33": "Hebrew Letter Dalet",
        "1": "One",
        "\U0001f600": "Emoji: Grinning Face",
        "\u0080": "Control",
        "\u00f6": "Latin",
    }
    assert list(json.loads(canonical_bytes(value))) == [
        "\r",
        "1",
        "\u0080",
        "\u00f6",
        "\u20ac",
        "\U0001f600",
        "\ufb33",
    ]


def test_canonical_golden_bytes_and_domains():
    value = {"z": [None, True, False, 1], "a": '\n"\\é'}
    expected = '{"a":"\\n\\"\\\\é","z":[null,true,false,1]}'.encode()
    assert canonical_bytes(value) == expected
    assert (
        digest("intent", value) == hashlib.sha256(b"work-steward:intent:1\0" + expected).hexdigest()
    )
    assert digest("intent", value) != digest("dispatch", value)


@pytest.mark.parametrize(
    "data",
    [
        b'{"x":1,"x":2}',
        b'{"a":{"x":1,"x":2}}',
        b"1.0",
        b"1e0",
        b"NaN",
        b"Infinity",
        b'"\\ud800"',
        b"\xff",
        b"\xef\xbb\xbf{}",
        b"[" * 1000 + b"]" * 1000,
        b"9" * 5000,
        b"0" * 65537,
    ],
)
def test_reject_ambiguous_or_unbounded_json(data):
    with pytest.raises(ValidationError):
        parse_json(data)


@pytest.mark.parametrize("value", [1.0, float("nan"), MAX_INTEGER + 1, -MAX_INTEGER - 1, {1: "x"}])
def test_canonical_rejects_outside_profile(value):
    with pytest.raises(ValidationError):
        canonical_bytes(value)


def test_intent_roundtrip_and_immutability(intent):
    assert Intent.from_json(intent.canonical) == intent
    assert Intent.from_json(intent.canonical).intent_digest == intent.intent_digest
    with pytest.raises(FrozenInstanceError):
        intent.quantity = 5
    ref = EvidenceRef("resource-1", "eligible", "version-1")
    assert replace(intent, evidence_refs=(ref,)).intent_digest != intent.intent_digest


@pytest.mark.parametrize(
    "change",
    [
        {"quantity": True},
        {"quantity": 1.0},
        {"quantity": "1"},
        {"quantity": 0},
        {"resource_version": False},
        {"schema_version": True},
        {"schema_version": 2},
        {"capability": "payment.create"},
        {"canonicalization_version": "next"},
        {"consistency": "C0"},
        {"consistency": Consistency.C2},
        {"adapter_digest": "not-a-digest"},
        {"evidence_refs": []},
    ],
)
def test_intent_constructor_rejects_coercion_and_unknown_semantics(intent, change):
    with pytest.raises(ValidationError):
        replace(intent, **change)


def test_wire_schema_requires_all_keys_and_rejects_extras(intent):
    value = intent.as_object()
    value["quantity"] = None
    with pytest.raises(ValidationError):
        Intent.from_json(json.dumps(value).encode())
    for name in intent.as_object():
        value = intent.as_object()
        del value[name]
        with pytest.raises(ValidationError):
            Intent.from_json(json.dumps(value).encode())
    with pytest.raises(ValidationError):
        Intent.from_json(json.dumps({**intent.as_object(), "verified": True}).encode())


def test_material_changes_and_unicode_are_not_silently_normalized(intent):
    for field, value in {
        "account": "account-2",
        "resource": "resource-2",
        "quantity": 10,
        "business_effect_key": "event-2",
        "adapter_digest": "b" * 64,
    }.items():
        assert replace(intent, **{field: value}).intent_digest != intent.intent_digest
    assert (
        replace(intent, resource="é").intent_digest
        != replace(intent, resource="e\u0301").intent_digest
    )


@given(
    st.dictionaries(
        st.text(alphabet="abcé😀", min_size=1, max_size=5),
        st.integers(min_value=-MAX_INTEGER, max_value=MAX_INTEGER),
        max_size=8,
    )
)
def test_property_canonical_order_is_independent_of_input_order(value):
    reverse = dict(reversed(list(value.items())))
    assert canonical_bytes(value) == canonical_bytes(reverse)
    assert parse_json(canonical_bytes(value)) == value
