# ADR 0007: Governed local authority

Status: accepted.

## Decision

Separate reference and governed databases so model commands cannot bypass policy. [Authority](../../src/work_steward/authority.py) checks exact-intent approvals, current policy, evidence, and expiry in the transaction that admits an attempt or records its possible-send boundary. Policy changes require new approvals.

Scope evidence by account, capability, subject, and predicate to prevent reuse across unrelated actions. Preserve authority history and a clock floor on denial to prevent expired grants from reviving after clock rollback. Revocation fences unsent attempts; released senders remain possible effects. Unknown outcomes cannot be retried here.

## Boundary

Host code must authenticate actors and establish evidence provenance; proposal fields cannot supply these facts. Administrator bindings are immutable across reopens. Trusted Python callers are not isolated from each other.

Cached authority fields and persisted boundaries grant no transport access. [Engine dispatch](0008-synthetic-dispatch.md) supplies the separate wire and synthetic-proof checks. The clock floor covers committed observations under the storage assumptions, not independent trusted time.
