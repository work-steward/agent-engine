# Architecture and code map

The package currently provides reference components for a single-node execution kernel. The reusable engine comes first; a nontechnical workbench can later use the same contracts. The project aims to be self-hostable, with no mandatory closed service.

## Implemented components

| Component | Source | Executable behavior |
| --- | --- | --- |
| Immutable synthetic intent | [intent.py](../src/work_steward/intent.py) | [Schema, identity, and canonicalization tests](../tests/test_intent.py) |
| Restricted RFC 8785 serialization | [canonical.py](../src/work_steward/canonical.py) | Golden bytes, UTF-16 key ordering, bounds, and hash-domain separation in intent tests |
| Action reference model | [model.py](../src/work_steward/model.py) | [Legal-state relation, guarded transitions, evidence, and generated sequences](../tests/test_model.py) |
| Engine ledger and reservations | [ledger.py](../src/work_steward/ledger.py) and [schema](../src/work_steward/ledger_schema.py) | [Immutable bindings, atomic commits, concurrent writers, and process-crash recovery](../tests/test_ledger.py) |
| Synthetic destination | [store.py](../src/work_steward/simulator/store.py) and [server.py](../src/work_steward/simulator/server.py) | [HTTP, independent persistence, crashes, deduplication, and conditional effects](../tests/test_simulator.py) |

`Action` is an immutable, in-memory reducer. `legal_dimensions` defines permitted combinations of dispatch disposition, effect assessment, and reconciliation activity; transition methods enforce the attempt guards. `Observation` and `RepetitionProof` represent already admitted model facts. The package does not yet verify real receipts or evaluate caller permissions.

`Ledger` persists a closed set of these trusted model commands in a separate, organization-bound SQLite database. Immutable intent, provider-key/profile bindings, and business reservations cannot be replaced through its API. State, attempt changes, observations, and journal entries commit in one transaction with a current version check. This supplies storage semantics, not policy admission or permission to send; recording `send_possible` does not invoke transport.

The provider runs in its own process and SQLite database. Its committed effects survive client termination or provider restart, independently of the engine ledger. Test-only clock and completion controls are absent from the HTTP interface; the harness can inspect hidden state as an oracle, while a future controller must use only the public protocol.

## Constraints worth preserving

- Timeout, missing status, grant expiry, and worker lease expiry do not prove that an earlier request cannot execute later. Repetition needs evidence covering every relevant attempt.
- Local cancellation stops future authority; it cannot reverse remote effects or erase uncertainty. Confirmed effect, unresolved attempts, and human acceptance are separate facts.
- Business-effect identity, operation identity, provider idempotency key, and transmission attempt identity serve different scopes. Do not substitute one for another.
- An input's claimed authority or verification is data. Supported execution paths must enforce authority outside model-generated text.

The rationale and remaining design obligations are in the [ADRs](decisions/README.md). [Conformance gates](conformance.md) identify what the next implementation must demonstrate; the [threat model](threat-model.md) bounds those claims.
