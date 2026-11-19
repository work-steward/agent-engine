# Roadmap

The intent schema, in-memory reference model, and independently persisted provider simulator are implemented. Their behavior is exercised in [tests](../tests). Complete kernel guarantees remain pending.

## Next: durable kernel

1. Build the engine's SQLite ledger: immutable intent and provider-key bindings, business uniqueness reservations, atomic state/journal/attempt commits, and worker fencing.
2. Connect a trusted adapter and dispatcher. Bind the exact request to approved intent and durably record the possible-send boundary before transmission.
3. Admit typed provider evidence, reconcile uncertain outcomes, and permit repetition only under the supported proof rules.
4. Exercise engine crashes, revocation races, stale workers, and restart recovery against the independent provider. Meet the [conformance gates](conformance.md).

## Later

An independently usable engine needs a supported real connector, durable human approvals and model results, and an API/CLI. Choose the reference business workflow against familiarity, expert access, verifiability, external-effect semantics, recoverability, and cost; payment examples do not preselect that domain.

A nontechnical workbench follows on the same engine. General executable plugins, broad multi-agent orchestration, distributed scheduling, shared-runtime multi-tenancy, and automatic provider failover remain deferred. Validate each new supported boundary before extending its guarantees.
