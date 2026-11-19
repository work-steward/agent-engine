# Contributing

Read the [code map](docs/architecture.md) and [roadmap](docs/ROADMAP.md) before choosing work. Discuss substantial API or architecture changes in an issue, then submit a focused pull request against `main`.

## Checks

```sh
uv sync --frozen
make check
```

`make format` applies safe Ruff fixes and Python formatting. Review the diff, then rerun `make check`. Lint covers all Python, including repository scripts; Markdown and YAML have their own configurations. Local documentation links must resolve to repository files. CI runs the same commands.

## Changes and evidence

- Add a regression, property, concurrency, or process test when behavior changes. Match the test to the guarantee; a passing in-memory model test does not establish durable execution.
- Document a design decision when changing authority, external-effect handling, persistence, evidence, or a supported trust boundary. Explain the tradeoff and link to relevant code and tests.
- Keep prose selective: explain purpose, constraints, and non-obvious choices. Put current behavior in code and executable tests. Update existing guides instead of adding handoff documents, implementation journals, or duplicate specifications.
- Use synthetic fixtures. Never submit credentials or private business data; follow [SECURITY.md](SECURITY.md) for vulnerabilities.
- AI assistance is welcome. Contributors remain responsible for correctness, provenance, and license compatibility; disclose substantial assistance and third-party material in the PR.

## Review and licensing

A maintainer reviews external contributions. Security and execution-control changes require owner review, with independent review before any release that performs consequential actions. On private repositories under GitHub Free, these merge rules are procedural until enforced branch rules become available.

Prefer squash merges. A sole maintainer may merge their own work after recording self-review and validation. Submit only work you have the right to contribute under [Apache-2.0](LICENSE), retain third-party notices, and identify dependency licenses. No separate CLA is required.
