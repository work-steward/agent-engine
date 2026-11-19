# Kernel-proof threat model

Status: accepted design. Strict synthetic intent validation and reference/simulator behaviors are tested; the production enforcement boundary remains unimplemented. See [current evidence](IMPLEMENTATION_STATUS.md).

## Assets and supported environment

Protect local action authority, immutable intent/request identity, business uniqueness claims, policy and evidence versions, attempt provenance, and accurate representation of uncertain external effects. The proof runs on a trusted single host, with one engine instance, one organization, local SQLite storage, trusted application/build dependencies, and synthetic data/credentials only.

The controller, built-in adapter/dispatcher, policy/evidence admission code, database library, Python runtime, operating system, HTTP stack, and deployment configuration are trusted. A source/artifact hash identifies a selected build; it does not make dependencies untrusted or establish a reproducible build by itself.

## Boundaries and authority

| Component | Allowed authority | Excluded authority |
| --- | --- | --- |
| Typed proposal input | Request a bounded operation using the public schema. | Change policy, satisfy its own evidence requirements, choose arbitrary URLs, access credentials, or directly transmit effects. |
| Trusted controller | Admit transitions under current policy; write authoritative state and journal. | Infer remote finality from local timeout or erase unresolved attempts. |
| Trusted dispatcher/adapter | Construct the one supported mapping and transmit after its durable boundary. | Broaden target/account/material fields, retry implicitly, or bypass admission. |
| Simulator provider | Apply/report synthetic effects under its selected profile; keep independent durable state. | Write the engine ledger or mint engine authorization. |
| Test harness/oracle | Schedule faults and inspect hidden state for test assertions. | Supply hidden knowledge to the controller's reconciliation path. |

The separate provider process is a crash/failure boundary. Shared OS-user permissions are not malicious-process isolation. The proof does not execute arbitrary untrusted code. The eventual model/worker/extension process boundary requires its own implementation and adversarial tests before support.

## In-scope failures and hostile inputs

Malformed proposals and provider responses; authority claims embedded in data; duplicate commands/events; material request substitution; unsupported capabilities/consistency; stale/changed evidence; duplicate business keys; concurrent/stale workers; revocation races; engine/provider process crashes; lost/delayed responses; delayed request arrival; finite idempotency retention; contradictory observations; and selected accidental secret-pattern exposure in repository checks.

The transport is the trusted path for the synthetic provider, not a general HTTP client exposed to proposals. Explicit destinations, closed schemas, no proxy/redirect/retry, and bounded observations reduce supported-path ambiguity. No production network credentials or customer records enter the proof.

## Exclusions and limits

- Malicious host/root administrator, privileged dispatcher compromise, dishonest database/storage, and arbitrary executable plugins with raw credential/network access.
- A provider lying about guarantees or violating its documented finality/idempotency contract. Injected contradictions should suspend the controller but do not establish independent ground truth.
- Power-loss/hardware durability guarantees beyond the specified storage assumptions; stale-backup restoration, disaster-recovery epochs, off-host audit anchoring, and tamper-proof audit.
- Multi-host deployment, shared-runtime multi-tenancy, production authentication, encrypted sensitive-context storage, and a production credential broker.
- Prompt-injection immunity across arbitrary generated content. The supported typed input path must not interpret data as authorization; no model integration or general taint tracking is demonstrated.

## Handling uncertainty and incidents

Fail closed on invalid input, stale authority, unknown schema, unsupported consistency, failed transactions, or adapter mismatch. A timeout or unavailable database does not authorize retransmission. Preserve possibly sent attempts and reservations, fence stale local writers, stop new admissions as needed, and reconcile only through currently authorized methods. No automatic compensation is supported. Never imply that local revocation reverses remote effects.

AC-12 can only be demonstrated here as absence of privileged exposure through the supported typed proposal path and synthetic fixtures. It remains unimplemented and untested; future executable-worker isolation is a separate claim. Repository CI's limited credential patterns are not complete secret scanning or runtime secrecy evidence.
