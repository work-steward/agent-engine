# Repository and release controls

The [workflow](../.github/workflows/repository-checks.yml), [lint configuration](../pyproject.toml), and [hygiene checker](../scripts/check_repository.py) are the maintained source for repository checks. CI uses full-SHA action pins, read-only tokens, disabled checkout credential persistence, ephemeral hosted runners, and bounded runtime. Pattern checks are not complete secret scanning.

Private repositories on GitHub Free cannot enforce all required-review/branch rules. Follow [CONTRIBUTING.md](../CONTRIBUTING.md) procedurally until a qualifying plan or public visibility enables enforcement. Repository files do not prove that organization settings are applied; administrators must verify settings in GitHub.

## Before public release

- Obtain the project lead's explicit visibility/release approval.
- Review all Git history, issues, artifacts, data, licenses, and notices; scan history for secrets and rotate exposed credentials.
- Verify owner-controlled access, required 2FA, branch protections, required checks, and stale-review dismissal. Enable native secret scanning/push protection where available.
- Verify outside-contributor workflow approvals, read-only default tokens, action restrictions, and spending limits. Keep secrets and persistent privileged runners away from untrusted contributions.
- Test confidential vulnerability and conduct-reporting channels and an independent conduct appeal route.
- Publish only demonstrated execution guarantees, with provider assumptions and a supported-version/security policy.
