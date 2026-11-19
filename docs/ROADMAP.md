# Roadmap

## Repository foundation

Preserve the handoff, define contribution and security procedures, configure available GitHub controls, and keep public release separately gated. Repository checks demonstrate hygiene only.

## First implementation milestone: kernel proof

The [design review](KERNEL_PROOF_DESIGN.md) proposes Python/SQLite, concrete lifecycle and retry contracts, an independent simulator, and a [conformance evidence matrix](conformance.md). These remain design specifications; no runtime invariant has implementation or test evidence yet.

1. Review the proposed ADRs and contracts for canonicalization, state transitions, transaction isolation, fencing, and process boundaries. Carry remaining implementation details into small PRs under those contracts.
2. Build a machine-checkable state model and deterministic external-system simulator.
3. Implement the smallest durable action ledger with atomic event/state/attempt commits and business-effect uniqueness.
4. Bind trusted adapter requests to approved intent, admit attempts under current authorization, and record the potentially-sent boundary before transmission.
5. Reconcile unknown outcomes conservatively; require safe-repetition proof before retry.
6. Demonstrate AC-01–AC-12 within documented assumptions through mapping, crash, revocation, evidence, and concurrency tests.

Exit criteria are in handoff sections 6, 7, and 10 and refined in the conformance matrix. Each supported invariant needs implementation references, named tests and reproducible evidence with assumptions and finite exploration bounds. Do not claim these criteria are met by bootstrap CI or simulated exception tests alone.

## Later gates

An independently usable engine adds a real adapter with tested provider guarantees, durable approvals, API/CLI, and a reviewed reference workflow. The nontechnical workbench follows on that engine. General multi-agent orchestration, connector marketplaces, and distributed deployment remain deferred.
