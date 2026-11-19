"""Closed, integer-only JSON profile over the RFC 8785 canonicalization implementation."""

import hashlib
import json
from typing import Literal

import rfc8785

MAX_INTEGER = 2**53 - 1
MAX_INPUT_BYTES = 65_536


class ValidationError(ValueError):
    """Input is outside the supported closed schema or canonicalization profile."""


def integer(value: object, name: str, *, minimum: int = 0) -> int:
    if type(value) is not int or not minimum <= value <= MAX_INTEGER:
        raise ValidationError(f"{name} must be an exact integer in [{minimum}, {MAX_INTEGER}]")
    return value


def text(value: object, name: str, *, limit: int = 128) -> str:
    if type(value) is not str or not 1 <= len(value) <= limit:
        raise ValidationError(f"{name} must be a nonempty string of at most {limit} characters")
    if any(ord(c) < 32 or 0xD800 <= ord(c) <= 0xDFFF for c in value):
        raise ValidationError(f"{name} contains unsupported characters")
    return value


def closed_object(value: object, keys: set[str]) -> dict:
    if type(value) is not dict or set(value) != keys:
        raise ValidationError("Object fields do not match the supported schema")
    return value


def _pairs(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValidationError("Duplicate JSON object key")
        result[key] = value
    return result


def _reject_number(_: str) -> None:
    raise ValidationError("Floating-point and non-finite numbers are unsupported")


def parse_json(data: bytes) -> object:
    if type(data) is not bytes or len(data) > MAX_INPUT_BYTES:
        raise ValidationError("JSON input exceeds the byte limit or is not bytes")
    try:
        value = json.loads(
            data.decode("utf-8"),
            object_pairs_hook=_pairs,
            parse_float=_reject_number,
            parse_constant=_reject_number,
        )
        _validate_tree(value)
        return value
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise ValidationError("Malformed or deeply nested JSON") from exc


def _validate_tree(value: object, depth: int = 0) -> None:
    if depth > 8:
        raise ValidationError("JSON nesting limit exceeded")
    if value is None or type(value) is bool:
        return
    if type(value) is int:
        integer(value, "JSON integer", minimum=-MAX_INTEGER)
    elif type(value) is str:
        if len(value) > 4096 or any(0xD800 <= ord(c) <= 0xDFFF for c in value):
            raise ValidationError("Unsupported JSON string")
    elif type(value) in (list, dict):
        if len(value) > 64:
            raise ValidationError("JSON collection limit exceeded")
        if type(value) is dict:
            for key in value:
                if type(key) is not str:
                    raise ValidationError("JSON object keys must be strings")
                _validate_tree(key, depth + 1)
            children = value.values()
        else:
            children = value
        for child in children:
            _validate_tree(child, depth + 1)
    else:
        raise ValidationError("Unsupported JSON value type")


def canonical_bytes(value: object) -> bytes:
    _validate_tree(value)
    try:
        result = rfc8785.dumps(value)
    except rfc8785.CanonicalizationError as exc:
        raise ValidationError("Cannot canonicalize value") from exc
    if len(result) > MAX_INPUT_BYTES:
        raise ValidationError("Canonical JSON exceeds the byte limit")
    return result


def digest(kind: Literal["intent", "dispatch"], value: object) -> str:
    if kind not in ("intent", "dispatch"):
        raise ValidationError("Unsupported digest domain")
    prefix = f"work-steward:{kind}:1".encode("ascii") + b"\0"
    return hashlib.sha256(prefix + canonical_bytes(value)).hexdigest()
