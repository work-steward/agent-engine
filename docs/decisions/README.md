# Architecture decisions

ADRs explain why a consequential choice was made and what constrains future changes. Keep mechanics in code and executable tests. New records use `NNNN-short-title.md` and a status of proposed, accepted, superseded, or rejected.

| ADR | Decision |
| --- | --- |
| [0001](0001-python-sqlite-proof.md) | Python and local SQLite |
| [0002](0002-action-state-and-send-boundary.md) | Independent state dimensions and a fenced transmission boundary |
| [0003](0003-retry-and-business-reservations.md) | Evidence-gated repetition and retained business reservations |
| [0004](0004-trusted-runtime-and-provider-boundary.md) | Independent simulator and explicit trust boundary |
| [0005](0005-intent-and-dispatch-binding.md) | Typed canonicalization and exact request binding |
| [0006](0006-conformance-and-claims.md) | Executable conformance evidence and bounded claims |

Original product-discovery notes remain in [Git history](https://github.com/work-steward/agent-engine/blob/b267f0d19aaca659c05094d10f2cd865461e0f81/docs/ARCHITECTURE_HANDOFF.md). They preserve provenance; current behavior is defined by the code/tests, with maintained constraints in these ADRs and the [roadmap](../ROADMAP.md).
