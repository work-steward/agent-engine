# Developing the reference kernel

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) from its official distribution, then run from the repository root:

```sh
uv sync --frozen
uv run --frozen ruff check src tests
uv run --frozen ruff format --check src tests
uv run --frozen pytest -q
python3 scripts/check_repository.py
git diff --check
```

The supported interpreter is CPython 3.13.18, pinned in `.python-version`. SQLite must be at least 3.37 with STRICT tables, WAL, FULL synchronization and foreign keys. Tests have been run locally on macOS arm64; CI targets Ubuntu. Subprocess readiness and request ordering use explicit pipe/select barriers, not sleeps. Hypothesis failures include a shrinking/replayable command trace; deterministic settings are in the test source.

## Run a synthetic destination

Create a scratch directory, then start the loopback provider:

```sh
mkdir -p .scratch
uv run --frozen work-steward-simulator --database .scratch/provider.sqlite
```

The first stdout line gives the bound `127.0.0.1` address and ephemeral port. This is an unauthenticated local **synthetic test tool**, not a production service. It refuses non-loopback binding and exposes no administrative endpoints. Use synthetic data only. Ignore the scratch directory in Git.

`POST /v1/effects` requires `Content-Type: application/json`, `X-WS-Attempt-ID`, and a closed JSON object containing `operation_id`, `account`, `resource`, positive integer `quantity`, and `resource_version` (null or an exact nonnegative integer). A keyed profile also requires `Idempotency-Key`. Duplicate/unknown material headers and JSON fields are rejected. The operation ID correlates effects; it does not secretly deduplicate them.

`GET /v1/effects?account=...&operation_id=...` is read-only and returns bounded records, a truncation flag, and `final_absence=false`. It may report an empty list while an older request can still arrive. No effect or finality should be inferred beyond the selected profile's documented evidence.

Profiles: `--profile permanent` (default), `none`, or `finite`. Finite retention uses a **logical clock**, advanced only by the test harness through `ProviderStore.advance_clock`; the default retention is 10 ticks. A permanent key matches the canonical request parameters within its account. Reusing it with changed parameters returns HTTP 409. Cache replay retains the original provider record/attempt identity. A restarting provider must use the same persisted profile, behavior, and retention settings.

Behaviors: `--behavior apply` (default), `pending`, `reject`, `drop_after_apply`, `contradictory_status`, or `duplicate_status`. Pending requests are released only by the harness through `ProviderStore.complete_pending`; C2 conditions are checked atomically at application time. `drop_after_apply` commits before closing the socket without a response. Contradictory/duplicate status behaviors intentionally test consumers' evidence handling.

Tests may inspect provider storage as an oracle and invoke harness controls out of band. The future controller must use only the public protocol. See [implementation status](IMPLEMENTATION_STATUS.md) for demonstrated behavior and the missing engine enforcement layer.
