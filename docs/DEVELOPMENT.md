# Development

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), Git, and Make. Use the Python version in [.python-version](../.python-version); the simulator also needs SQLite 3.37 or later with STRICT tables and WAL support.

```sh
uv sync --frozen
make check
```

`make lint` checks Python, Markdown, YAML, links, and repository hygiene. `make test` enforces 98% combined statement/branch coverage across the engine, scripts, and example, including threads and child processes. `make format` applies safe Ruff fixes and formatting; review its diff. CI uses the same targets. Start with the [inventory workflow](../examples/inventory/README.md) for an end-to-end run.

Rules live in [pyproject.toml](../pyproject.toml), [.pymarkdown.json](../.pymarkdown.json), and [.yamllint.yml](../.yamllint.yml). Python security exceptions are limited to test assertions and explicit synthetic subprocess launches. Markdown paragraph wrapping and a first-line H1 are optional so tables and GitHub template fragments remain practical. Local links are parsed as Markdown, must resolve to repository content with exact path casing, and cannot escape to private filesystem paths. External URLs are not fetched.

## Synthetic provider

```sh
mkdir -p .scratch
uv run --frozen work-steward-simulator --database .scratch/provider.sqlite
```

The first stdout line gives the bound loopback address and ephemeral port. This is an unauthenticated synthetic test tool. Use `--help` for its idempotency and fault profiles.

`POST /v1/effects` takes JSON fields `operation_id`, `account`, `resource`, positive integer `quantity`, and `resource_version` (null or an exact nonnegative integer). It requires `Content-Type: application/json`, `X-WS-Attempt-ID`, and, for keyed profiles, `Idempotency-Key`. See [request validation](../src/work_steward/simulator/store.py) and [protocol tests](../tests/test_simulator.py) for exact behavior.

`GET /v1/effects?account=...&operation_id=...` returns bounded status records with explicit truncation and `final_absence=false`. Missing records cannot rule out a delayed request. Fault profiles can deliberately duplicate or contradict status.

Synthetic protocol v2 adds read-only `GET /v1/profile` and `GET /v1/resources?account=...&resource=...`. The adapter conditions requests on `X-WS-Provider-ID`; effect receipts include the actual provider key. Instance IDs survive restart. Migrated legacy receipts retain null key evidence, never an inferred binding.

Finite retention uses a logical clock. The harness invokes `ProviderStore.advance_clock` and `complete_pending` out of band; these controls are absent from HTTP. A restarting provider must use its persisted profile configuration. Tests may inspect storage as an oracle; a future controller must use only the public protocol.

## Adding coverage

Use the existing tests as entry points for schema, transition, and provider changes. Subprocess readiness and ordering use explicit barriers instead of sleeps. Hypothesis supplies shrinking/replayable command traces. Preserve the [failure boundary](threat-model.md) when adding cases; provider/client termination is not an engine-ledger crash test.

## Engine ledger

`Ledger` stores trusted model events. Supply a typed `Intent`:

```python
from pathlib import Path
from work_steward.ledger import Command, Ledger

ledger = Ledger(Path(".scratch/engine.sqlite"), organization_id=intent.organization_id)
action = ledger.submit(intent, provider_key="stable-synthetic-key")
action = ledger.apply(
    intent.operation_id, expected_version=action.version, command=Command.EVALUATE
)
```

Inspect records with `get(operation_id)`, `history(operation_id)`, and `reservation(namespace, business_key)`. Identical submissions return current state; changed bindings conflict. Reservations have no release API.

Use one organization per local database, separate from provider storage. This profile bounds repetition proofs at 64 attempts; journal length is independent. History records command order and input, not verified caller identity. [Ledger tests](../tests/test_ledger.py) cover concurrency and process crashes; [storage assumptions](decisions/0001-python-sqlite-proof.md) and the [remaining execution gates](conformance.md) bound the guarantees.

## Governed operations

Create `Authority(path, organization_id=..., administrators=frozenset({...}))` for a separate governed database. Host code must authenticate control callers and establish evidence provenance. Reference `Ledger.apply` is disabled. `Engine` prepares requests, dispatches, reconciles, recovers, and cancels through this authority. It exposes only the synthetic loopback protocol; see [ADR 0008](decisions/0008-synthetic-dispatch.md).

Known v1/v2 databases upgrade atomically to v3 while retaining their mode and history. Old approvals have no request binding and cannot authorize transport until a prepared request receives fresh approval. Model authority never becomes a governed approval. Adapter/endpoint rebinding and stale-backup restores remain unsupported.
