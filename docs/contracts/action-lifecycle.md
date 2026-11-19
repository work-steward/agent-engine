# Action lifecycle contract, proof profile 1

Status: accepted design. In-memory reference transitions are implemented and tested; durable enforcement is not yet implemented. See [evidence and limits](../IMPLEMENTATION_STATUS.md).

## Authoritative records

- **Operation:** immutable intent and identity, current state version, dispatch disposition, effect assessment, reconciliation activity, references to attempts/evidence, and durable business reservation.
- **Grant:** operation/intent and exact request digests, approved adapter/destination/account, authoritative policy/evidence versions, credential reference if applicable, expiry, and one attempt ID. The proof uses synthetic credential references only.
- **Attempt:** immutable operation/request binding and generation; phase changes only through journaled transactions below. An operation may have at most one attempt in `admitted` phase. Earlier potentially sent attempts remain relevant after a later attempt is admitted.
- **Observation:** append-only typed provider/transport evidence attached to its original attempt. Evidence admission is a trusted transition, not a direct worker state write.
- **Journal:** ordered immutable events co-committed with every material authoritative change. Generation counters fence writes; event sequence records local order, not remote completion time.

Operation IDs, attempt IDs, and command IDs are scoped to the organization. Reject cross-organization references at every boundary. A repeated command ID returns the existing result only when command content matches. No identity can be rebound to different material content.

## Attempt phases and send authority

| Phase | Meaning | Permitted next phase |
| --- | --- | --- |
| `admitted` | Intent, exact request, grant, attempt, and event committed; transmission has not crossed its durable boundary. | `closed_without_send` or `send_possible` |
| `closed_without_send` | A transaction fenced the attempt before any send boundary. This attempt cannot transmit later. | None |
| `send_possible` | A successful transaction permitted one transmission; provider execution may have occurred or may still occur. | None; observations are separate records. |

Only the worker that successfully commits the unique `admitted -> send_possible` conditional transition may call transport, once, using that attempt's exact stored request. It must receive an unambiguous successful commit acknowledgement. Reading an existing `send_possible` row never grants send authority. A crash, uncertain commit, restart, redelivery, or lease takeover cannot resume that attempt's transmission. Any later transmission is a new attempt subject to the repetition contract.

A trusted dispatch worker must not forward a request before this transition. Revocation and takeover serialize with the transition; a worker that loses the transition cannot send. A worker that already won may transmit after revocation/takeover; keep that attempt unresolved and prevent unsafe repetition. A post-commit in-memory check may prevent a send but does not erase `send_possible` or establish remote finality.

## Supported legal operation states

Only combinations in this table are allowed in proof profile 1. An implementation must encode this relation explicitly; independent enums alone are insufficient.

| Dispatch disposition | Effect assessment | Reconciliation | Additional guard |
| --- | --- | --- | --- |
| `proposed` | `not_attempted` | `idle` | No attempt admitted. |
| `blocked`, `eligible` | `not_attempted`, `no_effect_confirmed` | `idle` | No active admitted attempt; eligibility alone grants no send authority. |
| `attempt_admitted` | `not_attempted`, `no_effect_confirmed` | `idle` | Current attempt is `admitted`; earlier attempts cannot violate the retry contract. |
| `attempt_admitted` | `unknown` | `idle` | Current attempt is `send_possible`, or is `admitted` under a persisted safe-repetition proof covering every prior possibly effective attempt. |
| `paused` | `not_attempted`, `no_effect_confirmed` | `idle`, `awaiting_human` | No active admitted attempt. |
| `paused` | `unknown`, `pending` | `scheduled`, `investigating`, `awaiting_human` | No new transmission without a separately admitted safe attempt. |
| `paused` | `conflicting` | `awaiting_human` | Contradiction unresolved; automatic admission denied. |
| `closed` | `not_attempted`, `no_effect_confirmed` | `idle` | No future dispatch authority for the operation. |
| `closed` | `effect_confirmed` | `idle`, `scheduled`, `investigating`, `awaiting_human` | Intended effect is confirmed; reconcile any remaining possible additional effects. Idle only when none remain unresolved. |
| `closed` | `unknown`, `pending` | `scheduled`, `investigating`, `awaiting_human` | Closure retains uncertainty and authorized reconciliation. |
| `closed` | `conflicting` | `awaiting_human` | Closure does not hide contradictory evidence. |

When an unknown/pending operation is safely re-admitted, disposition becomes `attempt_admitted`, effect remains `unknown`, reconciliation becomes `idle`, and the new attempt is `admitted` under the guard in the corresponding table row. This does not assert no earlier effect. `conflicting` is never eligible for automatic re-admission in this profile.

## Guarded transitions

1. **Propose:** validate and commit immutable intent, business reservation, state `proposed/not_attempted/idle`, and event atomically. Conflicting identity/reservation fails without a partial record.
2. **Evaluate:** move to `eligible` only with current policy, required admissible evidence, supported consistency, budgets, and no unresolved unsafe prior attempt. Otherwise block a never-sent/proven-no-effect operation; pause an uncertain operation. Evaluation results are version-bound and rechecked at admission.
3. **Admit:** revalidate inside the write transaction, including current generation, reservation ownership, and any repetition proof. Commit grant, exact request, unique attempt, state version, and event. Consume/reserve the applicable attempt budget here; a crash does not refund it implicitly.
4. **Cross send boundary:** revalidate grant, current policy/evidence, attempt phase, worker generation, and exact request/adapter binding. Atomically mark `send_possible`, set aggregate effect `unknown`, and append event. The unique acknowledged winner may invoke transport once outside the transaction.
5. **Observe:** append the observation. A current trusted controller evaluates evidence against the operation contract and all relevant attempts. A transport timeout, lost response, or worker exception yields no final-effect evidence. Before leaving dispatch handling or on recovery, unresolved outcomes move to `paused/unknown` with scheduled or human reconciliation.
6. **Reconcile:** separately authorize a read-only lookup, journal observations, and classify `pending`, `unknown`, final effect, final no-effect, or contradiction. A read authorization failure leaves existing effect evidence unchanged and moves reconciliation to `awaiting_human`; never claim remote failure because lookup is denied.
7. **Pause/close/revoke:** atomically fence any `admitted` attempt and mark it `closed_without_send`; retain every `send_possible` attempt. Revoking policy does not rewrite earlier approval/attempt records. Close stops new admissions but may leave effect `unknown`, `pending`, or `conflicting`. Reconciliation requires its own current authority.
8. **Repeat:** only the [repetition contract](retry-and-reservations.md) permits a new attempt. Closed operations never reopen automatically. A still-open paused operation may be re-evaluated under new authority; a revoked policy must first permit the action again.

## Evidence and aggregate outcomes

Claims bind organization, operation/attempt, subject and predicate, verifier/method/version, observed provider identity, evidence references, result, and validity conditions. Match the specific required predicate and pinned material version. Provider acceptance is `pending`, not `effect_confirmed`. Do not downgrade mandatory destination-atomic C2 preconditions to a local C1 read.

`no_effect_confirmed` requires evidence excluding both prior effect and later execution for every relevant attempt; current absence alone is insufficient. `effect_confirmed` requires admissible evidence that the intended business effect occurred. It closes future dispatch authority but does not assert that every attempt is resolved or that no extra effect is possible. Keep per-attempt assessments and reconcile any remaining uncertainty; report confirmed effect and unresolved attempts separately. Reconciliation can become idle only when every other attempt is unable to add an effect or covered by the same proven deduplication guarantee. Evidence for different targets or quantities cannot satisfy the intended effect predicate. Effect assessment alone is not business-objective success or human acceptance.

Contradictory final reports, or evidence of an unexpected additional effect, yield `conflicting` and human escalation. Preserve earlier claims and provenance; do not replace conflicting history with the newest timestamp. This proof profile does not automatically resolve conflicting evidence. Identical observations are deduplicated by source observation identity/content and cannot consume a second effect or erase prior evidence.

A stale worker may submit a trustworthy late observation for its original attempt. It cannot overwrite operation state or mint authority. Admission/deduplication of that observation and any resulting authoritative transition occur under the current controller, policy, and state version. A cancelled operation can therefore become `closed/effect_confirmed` or `closed/conflicting` without reopening dispatch.
