# Security policy

The package is an experimental reference model and synthetic provider. There is no production release or supported production execution environment. Fixes target `main`.

## Reporting vulnerabilities

Use Security → Report a vulnerability when private reporting is available. Otherwise request a private security contact from [@sohambhattacharjee](https://github.com/sohambhattacharjee), without including exploit details. Do not publish credentials, private data, or vulnerability details in public issues. No response-time SLA is promised.

Provide the affected revision, a minimal synthetic reproduction, impact, and relevant trust assumptions through the private channel. Coordinate disclosure with maintainers. Rotate exposed credentials; deleting a file does not remove it from history.

## Scope

Read the [threat model](docs/threat-model.md) for the supported boundaries. Model inputs representing policy or evidence are trusted test events, not caller authorization. The simulator is an unauthenticated loopback test tool. Neither component provides a sandbox for arbitrary executable agent code.

CI uses read-only tokens and ephemeral hosted runners. Do not run untrusted PR code with production secrets or persistent privileged runners. See [release controls](docs/REPOSITORY_SECURITY.md) before changing visibility or publishing a release.
