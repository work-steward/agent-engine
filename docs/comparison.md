# Comparison and limitations

Agent Engine is an experimental controller for approved external actions. Its current reference profile binds an intent, exact request, approval, attempts, and verified outcomes in one local SQLite ledger. It has one synthetic connector and a small inventory application.

Try it to inspect or challenge an approval-and-evidence controller locally. For a production workflow, evaluate an orchestration platform's documented features and the external service's effect contract; this repository has no supported production deployment or real connector.

## Different recovery boundaries

| Approach | Recovery unit | Work at the external-effect boundary |
| --- | --- | --- |
| Temporal | Durable Workflow history and Activity executions; Activities have configurable retries. | Design Activity side effects for re-execution, including provider idempotency and application authorization. See Temporal's [retry policies](https://docs.temporal.io/encyclopedia/retry-policies) and [Activity idempotency guidance](https://docs.temporal.io/activity-definition#idempotency). |
| Inngest | Durable steps; failed steps retry and completed results are reused. Event/function keys can deduplicate runs. | Inngest explicitly documents the gap where an external call succeeds before its result is saved, and recommends duplicate-safe effects. See [error handling](https://www.inngest.com/docs/durable-execution/guides-and-advanced/error-handling) and [idempotency](https://www.inngest.com/docs/durable-execution/guides-and-advanced/idempotency). |
| Application-side retries | Whatever request/task state the application persists; retry libraries can schedule attempts and backoff. | The application can implement stable keys, transactional records, approvals, destination conditions, and reconciliation. A timeout alone does not establish that a write failed; see [AWS's idempotent API discussion](https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/). |
| Agent Engine today | One approved action with durable attempt and send boundaries, request-bound receipts, and explicit uncertainty. | The supported synthetic controller checks current write authority before release, separately authorizes reads, and blocks uncertain repetition without its supported permanent-key proof. |

These are documented scope distinctions, not a feature-completeness score or comparative benchmark. Similar controls can be built in application code or on a workflow platform. This repository makes one narrow implementation and its fault tests available for inspection; it does not establish better safety or performance than those alternatives.

## Using it with an orchestrator

If you already use Temporal or Inngest, evaluate your external-effect contracts within that architecture. An integration would need to route every effectful attempt through the controller and ensure that Activity/step retries cannot replay a stored send boundary. Request preparation, current permission, and reconciliation still need a defined trust boundary. No maintained Temporal or Inngest integration exists here.

## Current limits

| Boundary | Supported scope or limit |
| --- | --- |
| Business effects | Synthetic inventory only. No real connector, credentials, production deployment, or business-objective correctness claim. |
| Host and identity | Trusted macOS/Linux host, local SQLite, one organization and provider account per ledger. Local POSIX identity; no external authentication service or arbitrary-code sandbox. |
| Provider | An honest implementation of the declared synthetic contract. Instance headers detect accidental replacement; they are not authentication. |
| Repetition | Uncertain unkeyed and finite-retention attempts cannot be repeated. Only the implemented permanent-key proof permits uncertain repetition. |
| Durability | Surviving authoritative engine/provider databases and documented storage assumptions. Stale restores, distributed scheduling, and failover are unsupported. |
| Intelligence and scale | No model execution, general workflow authoring, workbench, scalability benchmark, or comparative production evidence. |

The ordinary inventory example uses a destination resource-version condition. The README's `unsafe-retry` case deliberately omits it and uses an unkeyed provider, so a condition cannot conceal duplicate-write risk.

Evaluate the [specific safety claims](evaluation.md), [conformance evidence](conformance.md), and [threat model](threat-model.md) before extending the supported boundary. A successful demo or high coverage percentage is not proof of universal exactly-once effects.
