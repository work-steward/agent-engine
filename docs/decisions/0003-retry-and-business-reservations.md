# ADR 0003: Evidence-gated repetition and durable business reservations

- Status: accepted via the project lead's explicit merge authorization for PR #2 on 2026-11-19.
- References: D24, D45, D54–56, D72–74, D79, D93, D95; AC-02, AC-04–AC-09, AC-11.
- Product amendments: none.

## Context and decision

Follow the [retry and reservation contract](../contracts/retry-and-reservations.md). Operation identity, business-effect identity, provider idempotency key, and attempt identity remain distinct. Repeated client commands return the existing operation when material intent matches and reject attempts to rebind it.

Safe repetition is a typed, version-bound evidence record admitted by trusted code. It covers every earlier attempt that can still produce an effect, the proposed request, provider semantics, time/arrival bounds, and current preconditions. A human choosing to continue cannot turn missing evidence into proof. A policy override cannot silently weaken the required action contract.

The first proof can authorize repetition after all earlier attempts are fenced before send, after final no-effect evidence excludes delayed execution, or under tested permanent/scoped idempotency whose guarantees cover all possible earlier arrivals. Finite retention requires a provider-enforced arrival/expiry or equivalent guarantee; elapsed local time alone is insufficient. Unsupported cases stay paused or closed with reconciliation outstanding.

Reserve `(organization, capability namespace, business_effect_key)` transactionally for exactly one immutable operation. Preserve the claim when an attempt times out, the operation closes, or authority is revoked. A worker lease expiry never releases it. Successful effects retain their claim. Cancellation and compensation do not erase the original effect identity.

The first proof has no automatic reservation release or key recycling. If all attempts are proven unable to execute and the approved intent still applies, re-admit the same still-open operation under fresh authority. Closed operations remain closed. A changed intent requiring the same business identity needs a separately designed supersession protocol before support; it must not be smuggled in as a new key. Each synthetic action requires an explicit business-effect key; no key is inferred from matching parameters. A different operation proposing the same occupied key receives a conflict referencing the owner, not an implicit execution/intent rebind.

## Alternatives and consequences

Automatic retry on timeout and TTL-based reservation expiry improve apparent availability at the cost of duplicate effects. Always pausing after any failure is safe but would avoid testing legitimate idempotent recovery. Permanent reservations simplify proof and may block legitimate corrections until a later supersession design; that limitation is explicit.

## Validation and limitations

See [current implementation evidence](../IMPLEMENTATION_STATUS.md) for partial reference-model/simulator coverage; the full engine enforcement described here remains incomplete. Exercise delayed delivery after a negative lookup, retention expiry, overlapping requests, key parameter mismatch, confirmed effect followed by cancellation, and competing executions claiming one business key. Prove uniqueness only within this engine's surviving authoritative database; other applications and stale database restores remain outside that claim.
