# Contributing

Read the [code map](docs/architecture.md) and [roadmap](docs/ROADMAP.md) before choosing work. Discuss substantial API or architecture changes in an issue, then submit a focused pull request against `main`.

## Starting points

Choose an unassigned issue, describe your approach there, and keep the change within its acceptance criteria. The two issues labeled `good first issue` are intended as entry points; the process and property tests need more familiarity with the engine.

| Area | Scoped issue |
| --- | --- |
| Documentation | [Approval expiry versus reconciliation permission #15](https://github.com/work-steward/agent-engine/issues/15) |
| Fault scenario | [Read revocation after a send #16](https://github.com/work-steward/agent-engine/issues/16) |
| Process testing | [Provider restart with a paused sender #17](https://github.com/work-steward/agent-engine/issues/17) |
| Protocol analysis | [Finite retention and delayed senders #18](https://github.com/work-steward/agent-engine/issues/18) |
| Platform testing | [macOS walkthrough smoke check #19](https://github.com/work-steward/agent-engine/issues/19) |
| Property testing | [Bounded recovery schedules #20](https://github.com/work-steward/agent-engine/issues/20) |

Use the [evaluation guide](docs/evaluation.md) to find falsifiable claims and existing test entry points. Discuss changes to supported guarantees before expanding a contributor task into a new design.

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

A maintainer reviews external contributions. Security and execution-control changes require owner review, with independent review before any release that performs consequential actions. `main` requires pull requests, passing checks, and resolved conversations, including for administrators. While there is one maintainer, mandatory second-person approvals and enforced CODEOWNERS review are disabled.

Prefer squash merges. A sole maintainer may merge their own work after recording self-review and validation. Submit only work you have the right to contribute under [Apache-2.0](LICENSE), retain third-party notices, and identify dependency licenses. No separate CLA is required.
