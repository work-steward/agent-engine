# Repository and release controls

The [repository checks](../.github/workflows/repository-checks.yml), [security checks](../.github/workflows/security.yml), and [hygiene checker](../scripts/check_repository.py) define CI. Checks use full-SHA action pins, read-only tokens, disabled checkout credential persistence, ephemeral hosted runners, and bounded runtime. Security CI scans history with checksum-pinned Gitleaks and audits locked dependencies on PRs, `main`, and weekly. The [scanner configuration](../.gitleaks.toml) permits one exact synthetic enum string; no credential class, file, or directory is excluded.

Private repositories on GitHub Free cannot enforce all required-review/branch rules. Follow [CONTRIBUTING.md](../CONTRIBUTING.md) procedurally until a qualifying plan or public visibility enables enforcement. Repository files do not prove that organization settings are applied; administrators must verify settings in GitHub.

## Before public release

- Obtain the project lead's explicit visibility/release approval.
- Review all Git history, issues, artifacts, data, licenses, and notices; scan history for secrets and rotate exposed credentials.
- Verify owner-controlled access, required 2FA, branch protections, required checks, and stale-review dismissal. Enable native secret scanning/push protection where available.
- Verify outside-contributor workflow approvals, read-only default tokens, action restrictions, and spending limits. Keep secrets and persistent privileged runners away from untrusted contributions.
- Verify the private [security](../SECURITY.md) and [conduct](../CODE_OF_CONDUCT.md) contacts. The initial project lead handles reports and appeals; an independent appeal route is not yet available.
- Publish only demonstrated execution guarantees, with provider assumptions and a supported-version/security policy.

After visibility changes, require `repository-hygiene`, `kernel-tests`, `secret-scan`, and `dependency-audit` before merging to `main`. Verify external-workflow approvals and enable native secret scanning, push protection, and private vulnerability reporting where available. These administrative controls are not established by this file.
