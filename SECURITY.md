# Security policy

The project is an experimental execution engine with a synthetic inventory workflow. There is no production release or supported production execution environment. Only `main` receives fixes; no released-version support or response-time SLA is promised.

## Reporting vulnerabilities

Use [GitHub's private vulnerability reporting](https://github.com/work-steward/agent-engine/security/advisories/new) or email [1.bhattacharjee.soham@gmail.com](mailto:1.bhattacharjee.soham@gmail.com). Do not publish credentials, private data, or vulnerability details in public issues.

Provide the affected revision, a minimal synthetic reproduction, impact, and relevant trust assumptions through the private channel. Coordinate disclosure with maintainers. Rotate exposed credentials; deleting a file does not remove it from history.

## Scope

Read the [threat model](docs/threat-model.md) for the supported boundaries. Model inputs representing policy or evidence are trusted test events, not caller authorization. The simulator is an unauthenticated loopback test tool. Neither component provides a sandbox for arbitrary executable agent code.

CI uses read-only tokens and ephemeral hosted runners. Do not run untrusted PR code with production secrets or persistent privileged runners. See [release controls](docs/REPOSITORY_SECURITY.md) before changing visibility or publishing a release.
