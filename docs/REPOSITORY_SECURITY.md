# Repository and release controls

The [repository checks](../.github/workflows/repository-checks.yml), [security checks](../.github/workflows/security.yml), and [hygiene checker](../scripts/check_repository.py) define CI. Checks use full-SHA action pins, read-only tokens, disabled checkout credential persistence, ephemeral hosted runners, and bounded runtime. Security CI scans history with checksum-pinned Gitleaks and audits locked dependencies on PRs, `main`, and weekly. The [scanner configuration](../.gitleaks.toml) permits one exact synthetic enum string; no credential class, file, or directory is excluded.

`main` requires pull requests, up-to-date passing checks, resolved conversations, and linear history, including for administrators. Force pushes and deletion are blocked. The initial sole-maintainer review policy is explicit in [CONTRIBUTING.md](../CONTRIBUTING.md). Repository files do not prove settings are applied; administrators must verify them in GitHub.

## Before public release

- Obtain the project lead's explicit visibility/release approval.
- Review all Git history, issues, artifacts, data, licenses, and notices; scan history for secrets and rotate exposed credentials.
- Verify owner-controlled access, required 2FA, branch protections, required checks, and stale-review dismissal. Enable native secret scanning/push protection where available.
- Verify outside-contributor workflow approvals, read-only default tokens, action restrictions, and spending limits. Keep secrets and persistent privileged runners away from untrusted contributions.
- Verify the private [security](../SECURITY.md) and [conduct](../CODE_OF_CONDUCT.md) contacts. The initial project lead handles reports and appeals; an independent appeal route is not yet available.
- Publish only demonstrated execution guarantees, with provider assumptions and a supported-version/security policy.

Required checks are `repository-hygiene`, `kernel-tests`, `secret-scan`, and `dependency-audit`, bound to GitHub Actions. Native secret scanning, push protection, private vulnerability reporting, and CodeQL default setup for Python and GitHub Actions are enabled. External-contributor workflows require approval. Recheck these administrative controls after settings changes.
