# Roadmap

## Repository foundation

Preserve the handoff, define contribution and security procedures, configure available GitHub controls, and keep public release separately gated. Repository checks demonstrate hygiene only.

## First implementation milestone: kernel proof

1. Resolve typed canonicalization, state transitions, transaction isolation, fencing, and process boundaries in focused ADRs. Choose language and storage against those requirements.
2. Build a machine-checkable state model and deterministic external-system simulator.
3. Implement the smallest durable action ledger with atomic event/state/attempt commits and business-effect uniqueness.
4. Bind trusted adapter requests to approved intent, admit attempts under current authorization, and record the potentially-sent boundary before transmission.
5. Reconcile unknown outcomes conservatively; require safe-repetition proof before retry.
6. Demonstrate AC-01–AC-12 within documented assumptions through mapping, crash, revocation, evidence, and concurrency tests.

Exit criteria are in handoff sections 6, 7, and 10. Do not claim these criteria are met by bootstrap CI.

## Later gates

An independently usable engine adds a real adapter with tested provider guarantees, durable approvals, API/CLI, and a reviewed reference workflow. The nontechnical workbench follows on that engine. General multi-agent orchestration, connector marketplaces, and distributed deployment remain deferred.
