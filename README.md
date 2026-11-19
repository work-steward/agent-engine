# Work Steward — Agent Engine

Dependable, inspectable execution for AI-assisted business workflows.

Work Steward aims to give teams control over what an agent may do, durable records of what it attempted, and explicit handling of uncertain outcomes. It is fully self-hostable by design.

**Status: experimental intent schema, in-memory action model, and independent provider simulator. The durable execution engine is not implemented. Not suitable for production consequential actions.**

The first milestone is a small execution kernel with a deterministic external-system simulator and failure-injection tests. Model integrations and a nontechnical workbench follow demonstrated execution guarantees.

## Start here

- [Architecture baseline and 100 product decisions](docs/ARCHITECTURE_HANDOFF.md)
- [Kernel-proof design review](docs/KERNEL_PROOF_DESIGN.md), [threat model](docs/threat-model.md), and [conformance obligations](docs/conformance.md)
- [Development commands](docs/DEVELOPMENT.md) and [implementation evidence and limits](docs/IMPLEMENTATION_STATUS.md)
- [Implementation roadmap](docs/ROADMAP.md)
- [Contributing](CONTRIBUTING.md), [governance](GOVERNANCE.md), and [security](SECURITY.md)
- [Repository protection and public-release checklist](docs/REPOSITORY_SECURITY.md)

AI proposes; trusted execution authority decides. Unknown external outcomes remain unknown until admissible evidence resolves them. There is no universal exactly-once guarantee against arbitrary providers.

## Repository checks

Run `uv sync --frozen`, `uv run --frozen pytest -q`, `uv run --frozen ruff check src tests`, and `uv run --frozen ruff format --check src tests`. Python 3.13.18 and the Python dependencies are pinned; see the development guide. `python3 scripts/check_repository.py` and `git diff --check` remain repository hygiene checks. Passing model/simulator tests does not demonstrate durable engine enforcement.

## License

Apache-2.0. Contributions use the same license. See [LICENSE](LICENSE).
