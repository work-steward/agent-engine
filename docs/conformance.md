# Kernel-proof conformance and acceptance

Status: accepted obligations with partial reference-model and simulator evidence. The durable engine is not implemented. See [implementation status](IMPLEMENTATION_STATUS.md), [intent tests](../tests/test_intent.py), [model tests](../tests/test_model.py), and [process/HTTP simulator tests](../tests/test_simulator.py). No complete runtime invariant is demonstrated yet.

## Evidence matrix

Each row must eventually link to implementation symbols, executable case names, and a reproducible report at a specific commit. A passing repository-hygiene workflow is not evidence for any row below.

| Invariant | Required cases and assertions | Present evidence |
| --- | --- | --- |
| AC-01 Durable intent/attempt before transmission | Crash at intent, admission, and send-boundary commits; failed/uncertain commit; oracle proves every received request has committed prerequisites. | Reference boundary semantics tested; durable engine/dispatcher absent. |
| AC-02 Immutable operation identity | Duplicate command, different execution, changed quantity/account, changed canonicalization; deny rebinding. | Closed immutable intent/canonicalization tested; persistent identity registry absent. |
| AC-03 Intent/request mapping | Independently mutate destination, account, resource, quantity, key, body bytes, preconditions, headers, query, and adapter digest; deny before send. | Intent hash/material changes and provider input rejection tested; trusted adapter/binding absent. |
| AC-04 Current authority at admission | Separate-connection revocation/admission and revocation/send-boundary schedules; committed prior revocation wins; disclose the later remote race. | Model authority-change guards tested; authoritative policy/transaction linearization absent. |
| AC-05 Safe repetition | Accepted/lost response, delayed request after absent lookup, stale sender after lease takeover, finite retention expiry, scoped key mismatch; deny unsafe repeat and permit only covered cases. | Model witness guards and real delayed/expired-key provider scenarios tested; production proof admission absent. |
| AC-06 Typed admissible outcome evidence | Accepted is pending; malformed/unrelated/duplicate/contradictory claims; all-attempt aggregation; no false finality. | Model aggregation/identity/contradiction tests pass; actual receipt verifier absent. |
| AC-07 Stale writer fencing | Conditional state-version/generation mismatch; only one send-boundary winner; late evidence admitted without stale overwrite authority. | Immutable model version/generation guards tested; durable concurrency enforcement absent. |
| AC-08 Cancellation/revocation semantics | Close before/after boundary, delayed effect after close, denied reconciliation; retain history/uncertainty and block future unauthorized dispatch. | Model close/revocation/late-observation semantics tested; engine recovery absent. |
| AC-09 Business uniqueness | Concurrent different executions, duplicate/mismatched intent, restart, cancelled/unknown/confirmed operation; claim stays unique and retained. | Designed; implementation/tests absent. |
| AC-10 Atomic state/journal | Fail each write, rollback, kill/restart, concurrent sequencing, storage errors; no partial authoritative state/event commit. | Provider persistence/restart tested independently; engine state/journal ledger absent. |
| AC-11 Mandatory consistency | C2 operation with C1-only provider must be denied; provider atomic precondition failure must not apply an effect. | Model C1/C2 denial and simulator atomic C2 races tested; engine enforcement absent and real support provider-dependent. |
| AC-12 Supported-path secrecy/mediation | Closed proposal schema, no URL/credential authority, synthetic-secret redaction and mandatory dispatcher path. No arbitrary-code isolation claim. | Designed; implementation/tests absent; executable-worker isolation deferred. |

## Test layers

1. **Reference model:** enumerate the supported legal-state relation; reject all other combinations; exercise every transition guard and illegal edge. Bound exploration explicitly and preserve counterexample traces.
2. **Deterministic scenarios:** named schedules for crash boundaries, lost responses, deferred provider acceptance, late results, duplicate status, contradictions, retention variants, policy/evidence changes, and worker takeovers. Include pure read-only reconciliation, unsupported consistency denial, and successful evidence-gated repetition.
3. **Property tests:** generate bounded sequences of commands, revocations, crashes/restarts, cancellations, invalidations, lease changes, and provider events. Compare durable implementation state/trace against the model and oracle assertions. Record seed and schedule; generated tests must not share a faulty transition function as both implementation and expected result.
4. **Process/transport/storage tests:** real local SQLite transactions and loopback HTTP, separate provider storage/process, forced engine termination and independent provider restart, multiple database connections, busy/storage failures, and explicit transport attempt counting. Exception injection supplements but does not replace termination tests.

The provider's externally visible protocol must model absence and delayed finality honestly. The hidden oracle can assert that an effect occurred even when the controller cannot know it; the correct controller result in that case may remain unknown. Provider behavior and controller knowledge must not share one transaction or a privileged status shortcut.

Use barriers and virtual time to reproduce ordering, expiry, and clock rollback; do not make race coverage depend on wall-clock sleeps. Tests must include a stale dispatcher paused after its successful send-boundary commit and resumed after takeover/revocation. Proof gates must account for that request even when the new controller has fenced local state.

## Acceptance gates for implementation PRs

- State/serialization slice: closed schemas, golden canonicalization vectors, legal-state relation, illegal-transition tests, and explicit unsupported versions.
- Simulator slice: independently durable effects, observable protocol distinct from oracle, controlled delayed requests/responses and retention variants, no real business integration implied.
- Ledger slice: verified SQLite settings, atomic state/event/reservation/attempt commits, conditional fencing, independent-connection races, crash/restart behavior.
- Dispatch/recovery slice: exact mapping, no pre-boundary send or hidden retry, typed observations, authorization races, conservative all-attempt reconciliation, reservation retention, safe-repetition proof validation.
- Kernel proof gate: all supported matrix rows have implementation links, passing named scenarios and property/process tests, replayable reports, and disclosed assumptions/finite bounds. No unacknowledged remote result may become definitive non-effect merely because local execution failed.

Every implementation PR reports what is newly designed, implemented, tested, and provider-dependent. Unsupported guarantees stay explicit. Where an assumption cannot be enforced, revise the design or narrow the supported profile before marking a row demonstrated; do not silently weaken an invariant.

## Later release requirements

A real connector needs provider-specific evidence for idempotency scope/retention/arrival bounds, finality and status visibility, parameter/account binding, conditional effects, and reconciliation permissions. The independently usable engine also needs API/CLI and durable human-approval/model-result contracts. A nontechnical workbench and independent usability evidence follow later. Neither simulator conformance nor 500 supervised successes is blanket certification for arbitrary actions.
