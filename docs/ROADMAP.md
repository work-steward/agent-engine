# Roadmap

The [synthetic inventory MVP](../examples/inventory/README.md) implements durable approvals, bound dispatch, verified reconciliation, proof-gated repetition, and recovery against an independent provider. Integrated crash and stale-sender tests complete the three durable-kernel implementation stories. The [code map](architecture.md) and [conformance evidence](conformance.md) bound these claims.

## Before public release

| Pending story | Done when |
| --- | --- |
| Public release review | History, secrets, licenses, artifacts, tested claims, and reporting channels pass the [release controls](REPOSITORY_SECURITY.md). |
| Publication and enforced protections | The project lead approves visibility/release; administrators verify protections, required checks, access, and contributor workflow settings. Private GitHub Free remains the current choice. |

## Later

These stories follow the synthetic MVP; they do not block its release.

| Pending story | Done when |
| --- | --- |
| Authenticated operators | An external identity boundary enforces scoped approval, read, revocation, and audit permissions. |
| First real connector | Credential handling and provider-specific idempotency, status, conditions, and reconciliation have demonstrated evidence. |
| Durable model results | Model proposals/results have stable identity and persisted provenance; restart cannot silently rerun completed model work. |
| Broader workflow API/CLI | Supported workflow steps and transitions can be composed without embedding the inventory example. |
| Nontechnical workbench | Operators can inspect, approve, cancel, and investigate outcomes through the same governed engine. |

General executable plugins, broad multi-agent orchestration, distributed scheduling, shared-runtime multi-tenancy, and automatic provider failover remain deferred. Validate each new supported boundary before extending its guarantees.
