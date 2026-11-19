"""Immutable intent schema for the synthetic proof capability only."""

import re
from dataclasses import asdict, dataclass, fields
from enum import StrEnum

from .canonical import (
    ValidationError,
    canonical_bytes,
    closed_object,
    digest,
    integer,
    parse_json,
    text,
)


class Consistency(StrEnum):
    C0 = "C0"
    C1 = "C1"
    C2 = "C2"
    C3 = "C3"


@dataclass(frozen=True)
class EvidenceRef:
    subject: str
    predicate: str
    material_version: str

    def __post_init__(self) -> None:
        for name in ("subject", "predicate", "material_version"):
            text(getattr(self, name), name)


@dataclass(frozen=True)
class Intent:
    organization_id: str
    execution_id: str
    node_instance_id: str
    operation_id: str
    business_effect_namespace: str
    business_effect_key: str
    account: str
    resource: str
    quantity: int
    resource_version: int | None
    consistency: Consistency
    adapter_id: str
    adapter_digest: str
    evidence_refs: tuple[EvidenceRef, ...] = ()
    capability: str = "sim.effect.create"
    schema_version: int = 1
    canonicalization_version: str = "rfc8785-1"

    def __post_init__(self) -> None:
        for name in (
            "organization_id",
            "execution_id",
            "node_instance_id",
            "operation_id",
            "business_effect_namespace",
            "business_effect_key",
            "account",
            "resource",
            "adapter_id",
        ):
            text(getattr(self, name), name)
        integer(self.quantity, "quantity", minimum=1)
        if self.resource_version is not None:
            integer(self.resource_version, "resource_version")
        if type(self.consistency) is not Consistency:
            raise ValidationError("consistency must be a supported typed requirement")
        if self.consistency in (Consistency.C2, Consistency.C3) and self.resource_version is None:
            raise ValidationError("Atomic consistency requires a resource version")
        if type(self.adapter_digest) is not str or not re.fullmatch(
            "[0-9a-f]{64}", self.adapter_digest
        ):
            raise ValidationError("adapter_digest must be a SHA-256 hex digest")
        if type(self.evidence_refs) is not tuple or len(self.evidence_refs) > 32:
            raise ValidationError("evidence_refs must be a bounded immutable tuple")
        if any(type(ref) is not EvidenceRef for ref in self.evidence_refs):
            raise ValidationError("Unsupported evidence reference")
        if self.capability != "sim.effect.create" or type(self.schema_version) is not int:
            raise ValidationError("Unsupported capability or schema")
        if self.schema_version != 1 or self.canonicalization_version != "rfc8785-1":
            raise ValidationError("Unsupported schema or canonicalization version")

    def as_object(self) -> dict:
        value = asdict(self)
        value["consistency"] = self.consistency.value
        value["evidence_refs"] = [asdict(ref) for ref in self.evidence_refs]
        return value

    @property
    def canonical(self) -> bytes:
        return canonical_bytes(self.as_object())

    @property
    def intent_digest(self) -> str:
        return digest("intent", self.as_object())

    @classmethod
    def from_json(cls, data: bytes) -> "Intent":
        value = dict(closed_object(parse_json(data), {field.name for field in fields(cls)}))
        refs = value["evidence_refs"]
        if type(refs) is not list or len(refs) > 32:
            raise ValidationError("Invalid evidence references")
        value["evidence_refs"] = tuple(
            EvidenceRef(**closed_object(ref, {"subject", "predicate", "material_version"}))
            for ref in refs
        )
        try:
            value["consistency"] = Consistency(value["consistency"])
        except (TypeError, ValueError) as exc:
            raise ValidationError("Unsupported consistency requirement") from exc
        return cls(**value)
