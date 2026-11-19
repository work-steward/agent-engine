# ADR 0003: Repetition evidence and business reservations

Status: accepted; durable reservations and real proof admission pending.

## Decision

Keep operation, business-effect, provider-key, and attempt identities distinct. The [model](../../src/work_steward/model.py) has a narrow permanent-key repetition witness; it is a trusted model fact, not a provider attestation.

Another transmission needs current authority and evidence covering every earlier potentially effective attempt: fenced before send, final no-effect excluding later execution, or a supported idempotency guarantee. A timeout or negative lookup is insufficient. Finite retention needs a provider-enforced arrival bound; local expiry alone cannot stop an old sender arriving later.

The engine must reserve `(organization, capability namespace, business_effect_key)` for one immutable operation. Reservations survive cancellation, revocation, crashes, success, and uncertainty. No automatic key recycling or release is supported. Identical repeat commands return the same operation; another operation claiming the key conflicts. Changed material intent needs a reviewed supersession protocol.

## Rationale

Automatic timeout retry and lease-based reservation expiry can duplicate effects. Retaining reservations sacrifices availability until safe reconciliation or supersession exists. Uniqueness applies only within the surviving authoritative engine database, not other applications or stale restores.
