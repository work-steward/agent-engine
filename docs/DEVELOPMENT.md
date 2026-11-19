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

## Engine ledger

`Ledger` is a Python storage API for synthetic, trusted model events. Supply an existing typed `Intent`; it does not accept model text as authority:

```python
from pathlib import Path
from work_steward.ledger import Command, Ledger

ledger = Ledger(Path(".scratch/engine.sqlite"), organization_id=intent.organization_id)
action = ledger.submit(intent, provider_key="stable-synthetic-key")
action = ledger.apply(
    intent.operation_id, expected_version=action.version, command=Command.EVALUATE
)
```

Use `get(operation_id)`, `history(operation_id)`, and `reservation(namespace, business_key)` to inspect stored facts. Identical submissions return current state without resetting it or adding events. Changed intent, provider key, or capability profile conflicts; another operation cannot claim a reserved business key. Reservations have no expiry or release API.

Use one organization per local database, separate from provider storage. The ledger requires STRICT tables, foreign keys, WAL, FULL synchronization, and bounded lock waits. Unknown application/schema versions and organization mismatches are rejected. This profile permits up to 64 attempts per operation to bound serialized repetition proofs; journal history can contain more events. History records transaction order and command input, not verified caller identity or tamper-proof audit evidence. Storage failures propagate without returning a successful command.

[Ledger tests](../tests/test_ledger.py) use independent processes/connections and terminate writers before and after commit. They establish storage behavior under the stated filesystem assumptions, not power-loss durability or safe restoration of stale backups. Policy verification, real receipt admission, recovery scheduling, and effectful dispatch remain pending.
