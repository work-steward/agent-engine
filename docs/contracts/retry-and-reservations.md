# Repetition and business reservation contract, proof profile 1

Status: proposed; no implementation or provider guarantee has been demonstrated.

## Identities and uniqueness

Persist and distinguish organization, execution, operation, business-effect key, provider idempotency key, attempt ID, and command ID. The caller supplies a domain-scoped business-effect key. The synthetic proof requires one on every action. A matching quantity or target is not sufficient to infer whether two actions are duplicates or legitimate separate business events.

Enforce a unique constraint on `(organization, capability_namespace, business_effect_key)`, owned by one immutable operation and intent digest. Reserve it in the intent transaction. A repeat submission for the same operation ID returns it only if its entire immutable intent matches; otherwise reject the mismatch. A different operation ID attempting to claim an occupied business key receives a conflict with the existing operation reference, even when effect parameters match. Do not silently attach a new execution or rebind the existing intent. Cross-organization keys are isolated even if their textual values match.

In proof profile 1, reservations never expire or get recycled. Retain them after success, cancellation, revocation, timeout, process restart, or compensation. An execution may close while the reservation and action uncertainty remain. Do not use the worker lease, grant expiry, or provider key retention as the reservation lifetime. Retrying the same approved intent uses the same operation and reservation.

Changed material intent cannot be rebound to the old operation, old idempotency key, or an invented replacement business key. A legitimate amendment under the same business identity is unsupported until a reviewed supersession protocol exists. Distinct synthetic business events may use explicitly distinct keys; production domain definitions and uniqueness scopes require later connector/workflow design.

## Admission of another transmission

Every effectful transport invocation has a new attempt ID, an immutable request binding, an operation-bound grant, and the current authority checks. Admission is denied unless one of these cases covers **all** earlier potentially effective attempts:

| Case | Required evidence |
| --- | --- |
| No prior possible send | All earlier attempts are fenced `closed_without_send`; no `send_possible` attempt exists. |
| Definitive no effect | Admissible final evidence for every earlier possibly sent attempt, excluding delayed acceptance, pending work, and future execution. |
| Safe idempotent repetition | A tested/provider-supported guarantee ensures earlier and proposed requests cannot create an additional business effect under all possible arrivals and parameter bindings. |

The last case may include intrinsic idempotence or provider-keyed deduplication. It is not a generic boolean. Record a typed proof with operation/intent/proposed request digests, all covered attempt IDs and their request digests, provider account/capability/key scope, parameter matching rule, concurrency behavior, retention semantics, validity bounds, evidence references, verifier/version, and relevant policy/state versions. At admission, reject proof omissions, expired assumptions, changed evidence, or uncovered attempts.

Proof validation is closed trusted logic for the simulator's supported capability profiles. A model, human narrative, adapter self-declaration, or a timeout cannot supply the proof by assertion. Manual escalation can obtain missing evidence or close the operation; it cannot bypass AC-05 inside the supported protocol.

## Delayed requests and provider retention

An HTTP response can be lost after acceptance. An earlier worker can be suspended after crossing its send boundary and send later. An API can report no record while that request is still in transit. These cases remain potentially effective.

For provider-keyed repetition, use the same stable key, scope, and materially identical request, and establish parameter/concurrent-request behavior. Permanent retention is sufficient only under the provider's stated durable deduplication assumptions. Finite retention requires a proven bound ensuring all possible earlier arrivals remain covered, such as provider-enforced request expiry plus retention covering the entire admissible arrival interval. Local grant expiry, a client timeout, a process lease, and elapsed time on the engine do not enforce a remote arrival cutoff.

For this proof, a finite-retention profile without such a bound cannot authorize repetition after an uncertain transmission. A negative lookup also cannot authorize it unless its documented finality excludes every later execution being considered. Provider status is evidence under a capability contract, not access to a perfect oracle.

## Provider key and consistency requirements

Generate and persist the provider key before any send. Scope it to the exact provider account and capability; do not assume organization-local operation IDs are globally unique at a destination. Reuse it only for the same material operation. Never generate a new provider key merely to get past an ambiguous result or parameter mismatch.

New admission also requires current authorization/evidence, budgets, valid resource preconditions, and the originally required consistency level. Idempotency alone does not prove freshness, destination-account correctness, or satisfaction of C2. A provider's duplicate-result response is not necessarily final business-outcome evidence.

## Required negative examples

- Accepted then dropped response; lookup returns absent because delivery or indexing is delayed: pause.
- Old worker resumes after a newer worker owns the lease: its earlier possible send still counts.
- Finite key retention expires while old requests can still arrive: deny repetition.
- Final rejection of attempt A while attempt B remains pending: no aggregate no-effect claim.
- Same business key submitted by a different execution with a different quantity: reject conflict.
- Cancelled operation has no response yet: retain reservation and uncertainty.
- A human says to retry but no safe-repetition evidence exists: escalate or close without sending.
