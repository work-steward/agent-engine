# ADR 0006: Executable conformance evidence

Status: accepted.

## Decision

Treat [conformance obligations](../conformance.md) as acceptance gates, not evidence of implementation. Link claims to code and executable tests. Keep designed, implemented, tested, and provider-dependent statements distinct; avoid hand-maintained test totals or implementation journals.

Use an explicit reference model, deterministic fault schedules, property tests with replayable counterexamples, and real process/transport/storage tests. Exercise ordering through barriers and logical clocks. The controller sees only the modeled protocol; the test oracle may inspect hidden provider state to detect duplicates or false finality.

## Rationale and limits

Line coverage or one successful demo cannot establish crash/concurrency behavior. A model test does not prove the storage/HTTP implementation corresponds to it. Finite exploration provides bounded evidence, not universal proof, and simulator tests do not certify real providers. Human acceptance and observed effects are not interchangeable with business-objective success.
