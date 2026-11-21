# Conformance gates

Code and tests define implemented behavior. These stable acceptance IDs cover the single-host synthetic profile under the [threat model](threat-model.md); model tests alone do not establish durable execution.

## Existing tests

- [Intent tests](../tests/test_intent.py): closed schema, immutable values, canonicalization vectors, input bounds, and material identity changes.
- [Model tests](../tests/test_model.py): the legal-state relation, transition guards, retry witnesses, cancellation, contradictions, retained uncertainty, and generated command sequences.
- [Ledger tests](../tests/test_ledger.py): immutable operation/profile bindings, retained business reservations, atomic state/attempt/evidence/journal commits, concurrent writers, and real process death before/after commits. Inputs remain trusted model facts.
- [Authority tests](../tests/test_authority.py): exact approvals, scoped policy/evidence, expiry, clock rollback, revocation races, migration rollback, and approval process-crash boundaries. Control callers and evidence provenance remain trusted.
- [Simulator tests](../tests/test_simulator.py): independent provider/client processes, response loss, delayed requests, concurrent deduplication, finite retention, atomic conditional effects, and bounded protocol responses.
- [Engine tests](../tests/test_engine.py): exact wire binding, current authority, typed receipt admission, separate read grants, recovery, stale senders across provider restart, generated recovery schedules, and SQL failures around sending and observation commits.
- [Wire](../tests/test_synthetic.py) and [transport](../tests/test_transport.py) tests reject substitutions, ambiguous framing, unsupported contracts, redirects, and proxy overrides.
- [Inventory scenarios](../tests/test_inventory.py) use real process termination and a resumed old sender. [Supervisor tests](../tests/test_demo_failures.py) cover startup/cleanup failures and interrupted proposal recovery.

## Durable-kernel acceptance

Evidence is bounded to the implemented synthetic connector. External provider contracts remain unverified.

| ID | Required behavior | Evidence or remaining enforcement |
| --- | --- | --- |
| AC-01 | Commit immutable intent, attempt, and send boundary before any effectful transmission. | Prepared/per-attempt wire records, acknowledged release, commit-failure and process-crash cases |
| AC-02 | An operation identity cannot bind different material intent. | Ledger binding and concurrent-submission tests |
| AC-03 | Exact dispatch realizes the approved intent, account, destination, and adapter. | Independent material validator, approved request digest, persisted provider identity and artifact |
| AC-04 | Current policy/evidence at serialized admission; earlier revocation wins. | Admission/release transactions, revocation races, current evidence and expiry checks |
| AC-05 | Unknown prior outcome without safe-repetition evidence blocks another send. | Permanent-key coverage of every prior request; unkeyed and finite-window uncertain retries blocked |
| AC-06 | Typed evidence must support the required predicate; conflicting final claims escalate. | Request/key/attempt-bound receipts, current read permission, retained conflicting observations |
| AC-07 | Stale workers cannot overwrite state; trustworthy late observations remain attributable. | Generation/attempt fencing, nonterminal poll races, old sender after cancellation |
| AC-08 | Cancellation stops future authority and preserves prior effects/uncertainty. | Cancel/recover integration and independent provider persistence |
| AC-09 | Business-effect uniqueness survives cancellation, restart, and uncertainty. | Ledger reservation, restart, and concurrency tests; one surviving authoritative database |
| AC-10 | Material state changes and their journal events commit atomically. | Ledger storage-failure and real-process commit-boundary tests |
| AC-11 | Mandatory destination-atomic conditions cannot be replaced by a local recheck. | Provider instance and C2 resource-version conditions checked at the destination |
| AC-12 | Supported proposal paths expose no privileged secret or unmediated effect channel. | Typed local CLI inputs, fixed loopback adapter and mediated dispatch; arbitrary-code isolation deferred |

## Evidence required for acceptance

Preserve independent connections/processes, explicit barriers, logical clocks, and reproducible property traces when extending these cases. Exception injection complements actual process termination; it does not replace it.

An oracle may detect an effect the controller cannot observe. In that case, retaining an unknown result is correct. The controller must not inspect hidden simulator state to manufacture finality. Compare implementation behavior against independent expectations, not the same transition function as both implementation and oracle.

Real connectors need their own evidence for key scope/retention, parameter matching, concurrent requests, status visibility/finality, conditional effects, and reconciliation permissions. Publish the tested scope and remaining assumptions; simulator results do not certify arbitrary providers or business-objective success.
