# ADR 0007: Governed local authority

Status: accepted.

## Decision

Separate reference and governed databases. Governed operations cannot use the reference command API. [Authority](../../src/work_steward/authority.py) binds approvals to immutable intent, actor, policy revision, and expiry; policy changes require new approvals. Current account/capability/adapter/resource/quantity scope and evidence versions/expiry are checked in the write transaction at admission and the possible-send boundary.

Scope evidence by account, capability, subject, and predicate. Preserve policy, approval, evidence, and revocation history. Revocation fences unsent attempts; it cannot recall a released sender. Retain a nondecreasing observed clock floor even on authorization denial so clock rollback cannot revive an expired grant. Unknown outcomes cannot be retried through this controller.

## Boundary

This is a privileged local control API. Host code must authenticate `actor`, mediate access, and establish evidence provenance; proposal fields cannot supply these facts. Administrator bindings cannot be replaced on reopen. Python callers sharing the trusted runtime are not isolated from each other.

Cached action authority fields are projections. Only current controller checks authorize its state transitions; neither a returned action nor a persisted boundary grants transport access. Provider receipt verification, exact wire binding, and dispatch remain separate work. The clock floor covers committed observations under the existing storage assumptions, not an independent trusted-time service.
