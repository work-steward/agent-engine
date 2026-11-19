# Development

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), Git, and Make. Use the Python version in [.python-version](../.python-version); the simulator also needs SQLite 3.37 or later with STRICT tables and WAL support.

```sh
uv sync --frozen
make check
```

`make lint` runs repository-wide Ruff checks/formatting, Markdown and YAML linters, local-link validation, and file/workflow hygiene. `make test` runs pytest. `make format` applies safe Ruff fixes and formatting; inspect its diff before committing. CI runs the same targets.

Rules live in [pyproject.toml](../pyproject.toml), [.pymarkdown.json](../.pymarkdown.json), and [.yamllint.yml](../.yamllint.yml). Python security exceptions are limited to test assertions and explicit synthetic subprocess launches. Markdown paragraph wrapping and a first-line H1 are optional so tables and GitHub template fragments remain practical. Local links are parsed as Markdown, must resolve to repository content with exact path casing, and cannot escape to private filesystem paths. External URLs are not fetched.

## Synthetic provider

```sh
mkdir -p .scratch
uv run --frozen work-steward-simulator --database .scratch/provider.sqlite
```

The first stdout line gives the bound loopback address and ephemeral port. This is an unauthenticated synthetic test tool. Use `--help` for its idempotency and fault profiles.

`POST /v1/effects` takes JSON fields `operation_id`, `account`, `resource`, positive integer `quantity`, and `resource_version` (null or an exact nonnegative integer). It requires `Content-Type: application/json`, `X-WS-Attempt-ID`, and, for keyed profiles, `Idempotency-Key`. See [request validation](../src/work_steward/simulator/store.py) and [protocol tests](../tests/test_simulator.py) for exact behavior.

`GET /v1/effects?account=...&operation_id=...` returns bounded status records with explicit truncation and `final_absence=false`. Missing records cannot rule out a delayed request. Fault profiles can deliberately duplicate or contradict status.

Finite retention uses a logical clock. The harness invokes `ProviderStore.advance_clock` and `complete_pending` out of band; these controls are absent from HTTP. A restarting provider must use its persisted profile configuration. Tests may inspect storage as an oracle; a future controller must use only the public protocol.

## Adding coverage

Use the existing tests as entry points for schema, transition, and provider changes. Subprocess readiness and ordering use explicit barriers instead of sleeps. Hypothesis supplies shrinking/replayable command traces. Preserve the [failure boundary](threat-model.md) when adding cases; provider/client termination is not an engine-ledger crash test.
