# Roadmap

Immutable intents, the reference model, SQLite ledger/reservations, local policy/approvals, and independent provider simulator are implemented. [Tests](../tests) bound their behavior; caller authentication, provider-proof admission, and complete execution guarantees remain pending.

## Next: durable kernel

1. Connect a trusted adapter and dispatcher. Bind the exact request to approved intent and durably record the possible-send boundary before transmission.
2. Admit typed provider evidence, reconcile uncertain outcomes, and permit repetition only under the supported proof rules.
3. Exercise integrated engine crashes, stale workers, and restart recovery against the independent provider. Meet the [conformance gates](conformance.md).

## Later

An independently usable engine needs a supported real connector, durable human approvals and model results, and an API/CLI. Choose the reference business workflow against familiarity, expert access, verifiability, external-effect semantics, recoverability, and cost; payment examples do not preselect that domain.

A nontechnical workbench follows on the same engine. General executable plugins, broad multi-agent orchestration, distributed scheduling, shared-runtime multi-tenancy, and automatic provider failover remain deferred. Validate each new supported boundary before extending its guarantees.
