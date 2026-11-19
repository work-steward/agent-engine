# Security policy

## Supported versions

No production release exists. The architecture and repository bootstrap carry no production security or reliability guarantee. Security fixes initially target `main` only.

## Reporting a vulnerability

Do not disclose exploit details, credentials, or private business data in public issues or PRs. When GitHub private vulnerability reporting is enabled, use the repository's Security tab → Report a vulnerability. Otherwise request a private security contact from @sohambhattacharjee without including exploit details. A tested confidential reporting channel must exist before public launch; no response-time SLA is promised yet.

Include affected revision, trust assumptions, minimal synthetic reproduction, impact, and suggested mitigation through that private channel. Coordinate disclosure with maintainers. Rotate exposed credentials immediately; deleting a file does not remove secrets from history.

## Security scope

The handoff documents the proposed execution threat model. No runtime invariants have been implemented or tested yet. Host administrators, dishonest providers, untrusted executable connectors with raw network/credential access, and arbitrary API exactly-once behavior are outside the proposed initial guarantees.

Repository CI runs with read-only permissions and no deployment credentials. Never run untrusted PR code with privileged tokens, production secrets, or persistent self-hosted runners. Changes to workflows and release controls require owner review.
