# Architecture decision records

Use `NNNN-short-title.md`. Statuses: proposed, accepted, superseded, rejected.

Each record states context, decision, alternatives, affected D1–D100 and AC-01–AC-12 references, trust assumptions, validation evidence, limitations, and consequences. Explicitly identify product amendments requiring project-lead approval.

The project lead approved the kernel-proof recommendations on 2026-11-19, including the Python/SQLite direction and retaining Apache-2.0. The detailed records below were accepted through the project lead's explicit authorization to merge PR #2. Implementation evidence is tracked separately. The original handoff and its 100 product decisions remain unchanged; this does not ratify every earlier provisional refinement or Decision 101.

| ADR | Scope | Status |
| --- | --- | --- |
| [0001](0001-python-sqlite-proof.md) | Python, SQLite, durability and write serialization | Accepted |
| [0002](0002-action-state-and-send-boundary.md) | Operation state, fencing and transmission boundary | Accepted |
| [0003](0003-retry-and-business-reservations.md) | Repetition evidence and reservation lifecycle | Accepted |
| [0004](0004-trusted-runtime-and-provider-boundary.md) | Trusted runtime and independent simulator | Accepted |
| [0005](0005-intent-and-dispatch-binding.md) | Typed canonicalization and request mapping | Accepted |
| [0006](0006-conformance-and-claims.md) | Test evidence and supported claims | Accepted |
