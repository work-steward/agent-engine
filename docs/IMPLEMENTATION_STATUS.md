# Implementation evidence: reference model and simulator

This slice implements strict intent serialization, an immutable in-memory action model, and an independently persisted synthetic HTTP provider. It is not an execution engine: there is no durable engine ledger, authorization service, trusted dispatch adapter, real connector, or business workflow yet. D1–D100 remain unchanged.

## Implemented and exercised

| Component | Implementation | Evidence |
| --- | --- | --- |
| Closed synthetic intent | [Intent](../src/work_steward/intent.py), [canonicalization](../src/work_steward/canonical.py) | [Intent tests](../tests/test_intent.py): RFC 8785 UTF-16 ordering and golden bytes, domain-separated hashes, strict schema/coercion/version checks, duplicate-key and size/depth rejection, immutable values, Unicode distinctions, property-generated key ordering. |
| Action reference semantics | [Model](../src/work_steward/model.py) | [Model tests](../tests/test_model.py): all 144 disposition/effect/reconciliation combinations, send-boundary single use, local version/generation guards, revocation, retry-witness binding, finite-retention denial, late evidence, additional-effect contradictions, and confirmed effect with unresolved attempts. |
| Generated reference sequences | `LifecycleMachine` in model tests | Up to 40 commands in each of 80 deterministic Hypothesis examples. Failed commands preserve immutable state; sent attempts never become unsent; closed operations never reopen. These are finite model checks, not a proof over all executions. |
| Independent destination | [Provider store](../src/work_steward/simulator/store.py), [HTTP server](../src/work_steward/simulator/server.py) | [Simulator tests](../tests/test_simulator.py): separate processes, provider SIGKILL/restart, lost response plus client termination, concurrent permanent-key deduplication, key parameter/account scope, finite retention expiry, and an old sender released after an absent lookup. |
| Provider-side C2 | Atomic resource-version check and effect transaction | Two concurrent operations against version 0 yield one effect and one definitive rejection; pending requests evaluate their condition when they actually apply. This demonstrates the simulator's behavior only. |

Local validation on macOS arm64 used CPython 3.13.18 and SQLite 3.53.1: **82 tests passed**, Ruff lint and formatting passed. Python is pinned in `.python-version`; runtime/test dependencies and distribution hashes are recorded in `uv.lock`. CI runs the locked suite on an Ubuntu GitHub-hosted runner. A passing run is recorded on the implementation PR; no cross-platform or production claim follows from local results alone.

## Important boundaries

- `Action` is a pure reference reducer. Its policy facts and `Observation`/`RepetitionProof` inputs are trusted model events. A production controller must independently derive them from authoritative policy, immutable request bindings, and admissible evidence. They are not caller-provided authorization flags or provider attestations.
- The model's send-boundary transition is **in memory**. It grants no runtime network authority and has no crash durability. Simulator tests invoke HTTP directly as harness traffic. AC-01/AC-04/AC-07/AC-10 require the later durable controller/ledger implementation.
- `ProviderStore` is provider-side storage, not the engine ledger. Its atomic effects and deduplication cannot substitute for engine reservations, journal co-commits, admission, or worker fencing.
- The HTTP provider exposes only synthetic POST and read-only lookup methods. Clock advancement and pending-request release are harness-only Python controls. The oracle reads the provider database out of band; no model reducer imports the provider or accesses that oracle.
- Typed observations represent claims already admitted by a future verifier. The slice does not yet validate actual provider receipts into engine evidence. A simulator's contradictory-status behavior deliberately emits false final evidence for later controller testing.
- The permanent-key reference witness is deliberately narrow. Intrinsic idempotence, finite retention with provider-enforced arrival deadlines, and real-provider proof admission remain unsupported. Unknown finite-retention cases are denied.
- Lookup returns at most 16 records (32 when deliberately duplicating status), with a `truncated` flag and `final_absence=false`. A missing/truncated lookup is never proof of complete history or future non-execution.
- One observation may confirm an intended effect while another attempt remains uncertain. The model retains the positive claim and ongoing reconciliation. Distinct additional provider-effect IDs produce a conflict.

## Next implementation slice

Implement the engine's SQLite ledger: immutable intent and provider key binding, business-effect uniqueness reservations, state/event/attempt co-commits, authoritative version/generation checks, and crash recovery. Then connect the trusted adapter and dispatcher to that ledger, with typed receipt admission and conservative reconciliation. Add engine-crash tests rather than relabeling provider/client termination tests as engine evidence.

No runtime invariant is fully demonstrated by this slice. The [conformance matrix](conformance.md) remains the acceptance authority; entries identify partial evidence and the missing enforcement layer. The threat model's arbitrary-code isolation, real secrets, and real-provider limitations still apply.
