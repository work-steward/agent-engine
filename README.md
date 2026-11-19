# Work Steward — Agent Engine

Work Steward explores dependable execution for AI-assisted business workflows: bounded authority, inspectable attempts, and explicit handling of uncertain external effects.

The current package contains an immutable intent schema, an **in-memory reference model**, a SQLite ledger for trusted model commands and retained business-effect reservations, and a separately persisted synthetic HTTP provider. Authoritative policy, verified provider evidence, a production dispatcher, and real connectors remain pending. Use synthetic data only.

## Development

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) and run:

```sh
uv sync --frozen
make check
```

Python is pinned in [.python-version](.python-version); dependencies are locked in [uv.lock](uv.lock). `make lint` checks Python, Markdown, YAML, local documentation links, and repository hygiene. `make test` runs the reference-model, ledger, and simulator tests.

## Project guides

- [Architecture and code map](docs/architecture.md)
- [Development and simulator usage](docs/DEVELOPMENT.md)
- [Design decisions](docs/decisions/README.md)
- [Threat model](docs/threat-model.md), [conformance gates](docs/conformance.md), and [roadmap](docs/ROADMAP.md)
- [Contributing](CONTRIBUTING.md), [governance](GOVERNANCE.md), and [security reporting](SECURITY.md)

Licensed under [Apache-2.0](LICENSE).
