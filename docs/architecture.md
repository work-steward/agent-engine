# Architecture and code map

The engine uses Python and local SQLite on one host. This map links components to their executable behavior; product scope is in the [README](../README.md).

## Implemented components

| Component | Source | Executable behavior |
| --- | --- | --- |
| Immutable synthetic intent | [intent.py](../src/work_steward/intent.py) | [Schema, identity, and canonicalization tests](../tests/test_intent.py) |
| Restricted RFC 8785 serialization | [canonical.py](../src/work_steward/canonical.py) | Golden bytes, UTF-16 key ordering, bounds, and hash-domain separation in intent tests |
| Action reference model | [model.py](../src/work_steward/model.py) | [Legal-state relation, guarded transitions, evidence, and generated sequences](../tests/test_model.py) |
| Engine ledger and reservations | [ledger.py](../src/work_steward/ledger.py) and [schema](../src/work_steward/ledger_schema.py) | [Immutable bindings, atomic commits, concurrent writers, and process-crash recovery](../tests/test_ledger.py) |
| Local policy and approvals | [authority.py](../src/work_steward/authority.py) | [Scope, expiry, evidence, revocation races, migration, and approval durability](../tests/test_authority.py) |
| Synthetic destination | [store.py](../src/work_steward/simulator/store.py) and [server.py](../src/work_steward/simulator/server.py) | [HTTP, independent persistence, crashes, deduplication, and conditional effects](../tests/test_simulator.py) |

`Action` models dispatch, effect, and reconciliation separately. Its observations and repetition proofs are trusted model facts; provider-proof verification remains pending.

Reference databases accept trusted model commands. Governed databases require `Authority` checks in the transaction that admits an attempt or records its possible-send boundary. Host code must authenticate callers and establish evidence provenance; the controller exposes no transport. See [ADR 0007](decisions/0007-local-authority.md).

The simulator owns a separate process and database, keeping provider effects independent of engine state. Fault controls and hidden state belong to the test harness; controllers must use only the public protocol.

## Constraints worth preserving

- Timeout, missing status, grant expiry, and worker lease expiry do not prove that an earlier request cannot execute later. Repetition needs evidence covering every relevant attempt.
- Local cancellation stops future authority; it cannot reverse remote effects or erase uncertainty. Confirmed effect, unresolved attempts, and human acceptance are separate facts.
- Business-effect identity, operation identity, provider idempotency key, and transmission attempt identity serve different scopes. Do not substitute one for another.
- An input's claimed authority or verification is data. Supported execution paths must enforce authority outside model-generated text.

The [ADRs](decisions/README.md), [conformance gates](conformance.md), and [threat model](threat-model.md) explain design constraints and remaining obligations.
