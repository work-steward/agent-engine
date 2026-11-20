# Roadmap

The first public MVP is the [synthetic inventory workflow](../examples/inventory/README.md). It exercises durable approvals, bound dispatch, reconciliation, recovery, and proof-gated repetition without real integrations. The [code map](architecture.md) and [conformance evidence](conformance.md) define its scope.

## Before public release

Review the example and tested claims, complete the [release controls](REPOSITORY_SECURITY.md), and obtain explicit visibility/release approval. Repository visibility remains an administrative action.

## Later

Real connectors, externally authenticated operators, durable model results, and broader workflow APIs follow the synthetic milestone. Each connector needs evidence for its own idempotency, status, condition, and reconciliation semantics.

A nontechnical workbench follows on the same engine. General executable plugins, broad multi-agent orchestration, distributed scheduling, shared-runtime multi-tenancy, and automatic provider failover remain deferred. Validate each new supported boundary before extending its guarantees.
