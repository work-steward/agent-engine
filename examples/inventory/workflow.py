"""One warehouse, one SKU, and explicit stock-receipt approvals."""

import os
import time
from uuid import NAMESPACE_URL, uuid4, uuid5

from work_steward.authority import Policy
from work_steward.canonical import integer, text
from work_steward.engine import Engine
from work_steward.intent import Consistency, EvidenceRef, Intent
from work_steward.ledger import LedgerConflict, OperationNotFound
from work_steward.synthetic import ADAPTER_DIGEST, ADAPTER_ID, SUPPORTED_CONSISTENCY

ORGANIZATION = "inventory-demo"
WAREHOUSE = "demo-warehouse"
SKU = "DEMO-WIDGET"
CAPABILITY = "sim.effect.create"


def operator() -> str:
    if not hasattr(os, "getuid"):
        raise RuntimeError("The local inventory demo requires a POSIX user identity")
    return f"local-uid:{os.getuid()}"


def operation_id(request_id: str) -> str:
    text(request_id, "request_id")
    return str(uuid5(NAMESPACE_URL, "work-steward-inventory:" + request_id))


class Inventory:
    def __init__(self, engine: Engine, *, actor: str, clock=None):
        self.engine = engine
        self.authority = engine.authority
        self.actor = actor
        self.clock = clock or (lambda: time.time_ns() // 1_000_000_000)

    def setup(self):
        policy = Policy(
            WAREHOUSE,
            CAPABILITY,
            ADAPTER_ID,
            ADAPTER_DIGEST,
            frozenset({SKU}),
            frozenset({self.actor}),
            100,
            required_evidence=frozenset({"inventory-version"}),
        )
        current = self.authority.current_policy()
        if current is None:
            self.authority.configure(policy, actor=self.actor, expected_revision=0)
        elif current[1] != policy:
            raise LedgerConflict(
                "Demo policy changed; use a new directory rather than overwrite it"
            )
        self.authority.permit_read(
            "read-" + uuid4().hex,
            actor=self.actor,
            account=WAREHOUSE,
            capability=CAPABILITY,
            resources=frozenset({SKU}),
            expires_at=self.clock() + 3600,
            administrator=self.actor,
        )

    def refresh(self) -> dict:
        snapshot = self.engine.inventory(SKU, actor=self.actor)
        revision = self.authority.evidence_revision(
            account=WAREHOUSE, capability=CAPABILITY, subject=SKU, predicate="inventory-version"
        )
        self.authority.record_evidence(
            EvidenceRef(SKU, "inventory-version", str(snapshot["version"])),
            account=WAREHOUSE,
            capability=CAPABILITY,
            actor=self.actor,
            expected_revision=revision,
            expires_at=self.clock() + 300,
        )
        return snapshot

    def propose(self, request_id: str, quantity: int):
        integer(quantity, "quantity", minimum=1)
        identity = operation_id(request_id)
        try:
            old = self.engine.ledger.get(identity)
        except OperationNotFound:
            old = None
        if old is not None:
            if (
                old.intent.account,
                old.intent.resource,
                old.intent.quantity,
                old.intent.business_effect_key,
            ) != (WAREHOUSE, SKU, quantity, request_id):
                raise LedgerConflict("Business request already has a different stock adjustment")
            if self.engine.inspect(identity)["prepared_request"] is None:
                return self.engine.prepare(identity)
            return old
        snapshot = self.refresh()
        intent = Intent(
            ORGANIZATION,
            identity,
            identity,
            identity,
            "inventory.adjustment",
            request_id,
            WAREHOUSE,
            SKU,
            quantity,
            snapshot["version"],
            Consistency.C2,
            ADAPTER_ID,
            ADAPTER_DIGEST,
            (EvidenceRef(SKU, "inventory-version", str(snapshot["version"])),),
        )
        self.engine.ledger.submit(
            intent,
            provider_key="stock-" + identity,
            idempotency=self.engine.profile.idempotency,
            supported_consistency=SUPPORTED_CONSISTENCY,
        )
        return self.engine.prepare(identity)

    def approve(self, request_id: str):
        self.engine.prepare(operation_id(request_id))
        return self.authority.approve(
            operation_id(request_id),
            approval_id="approval-" + uuid4().hex,
            actor=self.actor,
            expires_at=self.clock() + 3600,
        )

    def report(self, request_id: str) -> dict:
        return self.engine.inspect(operation_id(request_id))
