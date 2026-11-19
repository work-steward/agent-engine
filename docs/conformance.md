# Conformance gates

Code and tests define implemented behavior. This checklist retains the acceptance obligations for the pending durable kernel; an in-memory model test or provider restart does not demonstrate engine durability.

## Existing tests

- [Intent tests](../tests/test_intent.py): closed schema, immutable values, canonicalization vectors, input bounds, and material identity changes.
- [Model tests](../tests/test_model.py): the legal-state relation, transition guards, retry witnesses, cancellation, contradictions, retained uncertainty, and generated command sequences.
- [Ledger tests](../tests/test_ledger.py): immutable operation/profile bindings, retained business reservations, atomic state/attempt/evidence/journal commits, concurrent writers, and real process death before/after commits. Inputs remain trusted model facts.
- [Simulator tests](../tests/test_simulator.py): independent provider/client processes, response loss, delayed requests, concurrent deduplication, finite retention, atomic conditional effects, and bounded protocol responses.

## Durable-kernel acceptance

The identifiers below are stable references for tests, changes, and incident reports. Storage obligations have executable evidence below; end-to-end authority and transmission guarantees remain pending.

| ID | Required behavior | Evidence or remaining enforcement |
| --- | --- | --- |
| AC-01 | Commit immutable intent, attempt, and send boundary before any effectful transmission. | Ledger storage exists; exact request binding and dispatcher pending |
| AC-02 | An operation identity cannot bind different material intent. | Ledger binding and concurrent-submission tests |
| AC-03 | Exact dispatch realizes the approved intent, account, destination, and adapter. | Trusted request mapping and independent validation |
| AC-04 | Current policy/evidence at serialized admission; earlier revocation wins. | Authoritative policy transaction |
| AC-05 | Unknown prior outcome without safe-repetition evidence blocks another send. | Production proof admission and retry controller |
| AC-06 | Typed evidence must support the required predicate; conflicting final claims escalate. | Provider receipt verifier |
| AC-07 | Stale workers cannot overwrite state; trustworthy late observations remain attributable. | Ledger versions/generations persist; worker runtime and trusted observation admission pending |
| AC-08 | Cancellation stops future authority and preserves prior effects/uncertainty. | Recovery and dispatch integration |
| AC-09 | Business-effect uniqueness survives cancellation, restart, and uncertainty. | Ledger reservation, restart, and concurrency tests; one surviving authoritative database |
| AC-10 | Material state changes and their journal events commit atomically. | Ledger storage-failure and real-process commit-boundary tests |
| AC-11 | Mandatory destination-atomic conditions cannot be replaced by a local recheck. | Connector eligibility and dispatch enforcement |
| AC-12 | Supported proposal paths expose no privileged secret or unmediated effect channel. | Runtime mediation; arbitrary-code isolation remains deferred |

## Evidence required for acceptance

Add named executable cases and implementation references as each invariant is enforced. Use independent database connections, explicit barriers, logical clocks, and reproducible property-test traces. Kill real processes at durable boundaries; exception injection alone is insufficient. Include an old sender resumed after revocation/takeover, an absent lookup before late delivery, and expiry of a provider's deduplication window.

An oracle may detect an effect the controller cannot observe. In that case, retaining an unknown result is correct. The controller must not inspect hidden simulator state to manufacture finality. Compare implementation behavior against independent expectations, not the same transition function as both implementation and oracle.

Real connectors need their own evidence for key scope/retention, parameter matching, concurrent requests, status visibility/finality, conditional effects, and reconciliation permissions. Publish the tested scope and remaining assumptions; simulator results do not certify arbitrary providers or business-objective success.
