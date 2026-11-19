# Work Steward — Agent Engine

Work Steward explores dependable execution for AI-assisted business workflows: bounded authority, inspectable attempts, and explicit handling of uncertain external effects.

The package provides immutable intents, an **in-memory reference model**, a SQLite ledger with retained business-effect reservations, a local policy/approval controller, and an independent synthetic HTTP provider. Caller authentication, provider-proof verification, a production dispatcher, and real connectors remain pending. Use synthetic data only.

## Development

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) and run:

```sh
uv sync --frozen
make check
```

Python is pinned in [.python-version](.python-version); dependencies are locked in [uv.lock](uv.lock). `make lint` checks Python, Markdown, YAML, local documentation links, and repository hygiene. `make test` covers the model, storage, authority, and simulator.

## Project guides

- [Architecture and code map](docs/architecture.md)
- [Development and simulator usage](docs/DEVELOPMENT.md)
- [Design decisions](docs/decisions/README.md)
- [Threat model](docs/threat-model.md), [conformance gates](docs/conformance.md), and [roadmap](docs/ROADMAP.md)
- [Contributing](CONTRIBUTING.md), [governance](GOVERNANCE.md), and [security reporting](SECURITY.md)

Licensed under [Apache-2.0](LICENSE).
