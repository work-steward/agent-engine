# Kernel proof: implementation design review

Status: accepted kernel-proof design via project-lead-authorized merge of PR #2 on 2026-11-19. The first reference components are implemented; the durable engine does not yet exist. See [implementation evidence](IMPLEMENTATION_STATUS.md).

The project lead approved the recommendations in chat on 2026-11-19: use Python and SQLite for a single-node proof, clarify action and reservation lifecycles, strengthen retry rules, specify a concrete trust boundary, and test with an independent simulated provider. Apache-2.0 remains the project license. These specifications do not establish tested guarantees or amend D1–D100. Decision 101 remains unanswered.

## Scope and decisions

| Record | Proposed implementation choice |
| --- | --- |
| [ADR 0001](decisions/0001-python-sqlite-proof.md) | CPython 3.13, one SQLite database on local storage, serialized write transactions and atomic state/event commits. |
| [ADR 0002](decisions/0002-action-state-and-send-boundary.md) | Separate operation dimensions, immutable attempt records, and a fenced durable transmission boundary. |
| [ADR 0003](decisions/0003-retry-and-business-reservations.md) | Explicit safe-repetition evidence; reservations survive cancellation and unresolved effects. |
| [ADR 0004](decisions/0004-trusted-runtime-and-provider-boundary.md) | Trusted controller/dispatcher and built-in adapter; provider in an independent process with its own durable state. |
| [ADR 0005](decisions/0005-intent-and-dispatch-binding.md) | Restricted typed JSON, RFC 8785 canonicalization, domain-separated hashes, exact simulator request binding. |
| [ADR 0006](decisions/0006-conformance-and-claims.md) | Traceable invariants, real process-crash tests, deterministic scheduling, and explicit limits on claims. |

The [action lifecycle](contracts/action-lifecycle.md), [retry/reservation contract](contracts/retry-and-reservations.md), and [intent/dispatch contract](contracts/intent-and-dispatch.md) supply the behavior that implementation and tests must share. The [threat model](threat-model.md) supplies the supported deployment boundary. The [conformance plan](conformance.md) supplies test obligations and evidence status.

## First vertical slice

Use only synthetic `sim.effect.create` operations. A request targets a simulator account/resource and an integer quantity. This is a test capability, not the product's real reference business workflow. The simulated destination can apply the effect, delay it, lose a response, or report conflicting evidence. One action is sufficient to exercise the contracts; there is no workflow scheduler, model integration, arbitrary code runner, credential broker, or production HTTP connector in this slice.

Implement in this order:

1. A typed reference state model with an explicit legal-state relation and guarded transitions; positive and negative canonicalization vectors.
2. An independently persisted provider simulator with deterministic scenario control and a loopback HTTP endpoint. Keep the test oracle separate from the controller's status protocol.
3. SQLite ledger, uniqueness claims, atomic journal, fencing, and explicit transaction boundaries.
4. One trusted request adapter, attempt admission, send-boundary commit, and exactly one transport invocation per admitted attempt. Disable implicit retries and redirects.
5. Observation admission, conservative reconciliation, and proof-gated repetition, including delayed-request and stale-worker cases.
6. Reproducible conformance evidence, subprocess crash/restart tests, and documented unsupported behavior.

These are small implementation PRs. Each updates the evidence matrix for the behavior it actually demonstrates. Avoid a multi-backend abstraction or generalized policy language.

## Review resolutions

- A missing provider record is not automatically evidence that a delayed request cannot execute later.
- A worker losing its lease does not stop a request already admitted to transmission.
- A reservation is not a worker lease. Closing an operation does not free its business-effect identity.
- A durable, fenced `closed_without_send` attempt can be distinguished from `send_possible`; absence of a response cannot make that distinction.
- Finite provider idempotency retention is insufficient when an earlier transmission may arrive after retention expires.
- The controller cannot read the simulator's hidden state to resolve uncertainty. A test may inspect that state only as an independent assertion oracle.
- The initial trusted runtime has no hostile executable worker. AC-12 cannot be reported as proof of an arbitrary-code sandbox.
- A confirmed intended effect can coexist with unresolved attempts; keep that positive evidence while continuing reconciliation. It does not establish business-objective success or absence of additional effects.

## Remaining decisions and release gates

Exact package versions and lockfiles, SQL schema/migration scripts, model data types, and test-case implementations belong to their implementation PRs under these contracts. A missing necessary guarantee triggers a narrow ADR revision, not a weaker test assertion.

A real connector and reference workflow require the D87 selection rubric and verified provider behavior at Stage 2. Sensitive production data, encrypted context storage, remote deployment/authentication, stale-backup restoration, untrusted executable workers, and distributed scheduling require later designs before support is claimed. The kernel proof uses synthetic data only.

GitHub Free private-repository review restrictions remain procedural. CI now checks repository hygiene and the initial model/simulator suite; it does not demonstrate the complete invariant set. [Setup status](../SETUP_STATUS.md) records repository protection limits.
