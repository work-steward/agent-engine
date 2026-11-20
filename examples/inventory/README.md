# Synthetic inventory workflow

Record a receipt of 10 `DEMO-WIDGET` units into `demo-warehouse`. The CLI proposes a version-conditional adjustment, obtains an explicit approval, and uses the engine to dispatch and reconcile it against a separate warehouse process. No credentials or model API are needed.

From the repository root on macOS or Linux:

```sh
uv sync --frozen
make demo
uv run --frozen python -m examples.inventory run --scenario lost-response
```

Each scenario retains its databases under `.scratch/inventory/<scenario>`. Use `--directory PATH` before the subcommand for a fresh run elsewhere. Repeated business request IDs keep their original intent and outcome.

| Scenario | Demonstrates |
| --- | --- |
| `success`, `duplicate` | One confirmed adjustment despite repeated submission |
| `revocation`, `stale-evidence` | Changed authority or stock evidence blocks dispatch |
| `lost-response`, `crash-after-send` | An applied change survives loss of the engine's receipt |
| `unsafe-retry` | An unconditional unkeyed change applies, its response disappears, and a requested retry is blocked |
| `crash-before-send` | Recovery fences an unsent attempt before a fresh attempt |
| `safe-retry` | A resumed old sender and a proven permanent-key retry produce one change |
| `unknown` | An empty lookup cannot resolve uncertainty; an unkeyed retry is blocked |

Inspect a completed run offline:

```sh
uv run --frozen python -m examples.inventory --directory .scratch/inventory/lost-response inspect receipt-001
```

For manual steps, use `propose REQUEST --quantity N`, `inspect REQUEST`, `approve REQUEST`, and `dispatch REQUEST` in the same directory. Recovery commands are `reconcile`, `recover`, `retry`, and `cancel`; `refresh` updates stock evidence. `--help` lists arguments. Inspection includes prepared bytes, approvals, attempts, admitted observations, rejected responses, and journal history.

The trusted local operator is the process's POSIX UID. Scripted runs approve their own synthetic proposal; this is not a multiuser approval service. Fault barriers live in the example harness, outside normal dispatch. The engine uses only the warehouse's public HTTP protocol. Replay safety assumes surviving authoritative databases and the declared synthetic provider contract; stale restores and real integrations are unsupported.

## Resolve the lost response

For the README's `unsafe-retry` case, keep the same terminal variable and reconcile the original request:

```sh
uv run --frozen python -m examples.inventory \
  --directory "$inventory_demo_dir/unsafe-retry" reconcile receipt-001
```

The output is the full operation history. Expect `effect` to become `effect_confirmed`, one entry in `attempts`, and a lookup response admitting a matching observation. No second adjustment is sent. `inspect receipt-001` in that same directory reads the history offline.

This case selects an unkeyed provider, drops the response after applying, and omits the destination version condition. The normal inventory proposal uses C2; `unsafe-retry` uses C0 to expose the duplicate-write risk. Re-proposing the same request with a different condition conflicts. Re-running a retained case preserves its outcome; use a fresh directory to reproduce the initial loss.
