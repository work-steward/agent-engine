# ADR 0006: Evidence-based conformance and bounded claims

- Status: accepted via the project lead's explicit merge authorization for PR #2 on 2026-11-19.
- References: D20, D47–53, D63–64, D77–79, D82–86, D91; AC-01–AC-12 under documented scope.
- Product amendments: none. No autonomy threshold or certification claim is established.

## Context and decision

Adopt the [conformance matrix](../conformance.md). Each invariant needs an implementation reference, named executable cases, preserved failure traces, and explicit assumptions before it can be marked demonstrated. Keep designed, implemented, tested, and provider-dependent status separate. Documentation-only CI does not advance runtime evidence status.

Use a pure reference model for legal-state tests, deterministic scenario schedules, and seeded property tests. Supplement these with actual subprocess termination and restart against a real SQLite database and independently persisted HTTP simulator. A synthetic exception inside one transaction is not a substitute for killing a process after a committed send boundary.

The harness controls clocks, provider responses/delivery, and crash barriers. It must explore races by controlling transaction/send barriers and separate database connections rather than relying on sleeps. Save the seed, event schedule, engine/provider versions, relevant configuration, and synthetic trace for each failure. The controller sees only its permitted protocol; the oracle may inspect provider state to detect duplicate effects and false claims.

Treat wall-clock rollback, restart, and expiry as explicit scenarios. An injected test clock controls expiry decisions, while database event sequence and generation counters establish local order. Conservative expiry with uncertain time denies new grants/repetition; it must not extend provider retention guarantees. Production-grade cross-host clock assurance is outside the proof.

## Alternatives and consequences

Line coverage and one successful demo do not establish crash or concurrency invariants. Random testing without replayable schedules is hard to debug. Formal reference-model exploration alone cannot prove the Python/SQLite/HTTP implementation corresponds to that model. All three levels are needed, with finite explored bounds disclosed.

## Validation and limitations

See [current implementation evidence](../IMPLEMENTATION_STATUS.md) for partial reference-model/simulator coverage; the full engine enforcement described here remains incomplete. Acceptance requires explicit evidence for every supported claim, including negative cases showing that prohibited behavior is denied. AC-12's restricted input-path checks cannot be advertised as untrusted-code isolation. Simulator results do not certify a real provider. Finite model/property tests are evidence under assumptions, not a mathematical proof over arbitrary executions.
