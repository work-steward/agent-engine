# Repository security and release gates

## Current bootstrap

The organization uses GitHub Free and the repository is private. Enforced rules and CODEOWNERS review gates for private repositories require a qualifying paid plan. CODEOWNERS, contribution rules, and CI files alone do not enforce merges. No runtime is implemented.

The bootstrap workflow uses a full-SHA-pinned checkout action, read-only contents permissions, no persisted checkout credentials, bounded runtime, and GitHub-hosted ephemeral runners. Dependabot proposes GitHub Actions updates weekly. The dependency-free hygiene script flags selected credential patterns, sensitive filenames, binary/large files, and unpinned actions. It is not a complete secret scanner and cannot protect against a malicious PR changing its own checks.

## Target GitHub settings (verify separately)

- Organization: no default repository access; owner-controlled member invitations, repository creation, visibility changes, and deletion/transfer; require 2FA for members where supported.
- Repository: private; disable private forks; only squash merges; delete merged branches; disable unused wiki, Pages, and deployments.
- Actions: read-only default token; prohibit workflow-created approvals; restrict allowed actions to needed sources; require approval for outside-contributor runs before public release; no secrets or persistent self-hosted runners for untrusted contributions.
- Dependencies: enable dependency graph, Dependabot alerts and security updates where available.
- Branch rules when eligible: protect `main` from force push and deletion; PRs required; required `repository-hygiene` check with up-to-date branch; resolve conversations; require owner approval for external changes and dismiss stale approvals. Restrict any owner bypass to explicit documented solo-maintainer merges. Independent review is needed before consequential-action releases.

## Public-release checklist

- [ ] Project lead separately authorizes making the repository public.
- [ ] Review the entire Git history, issues, artifacts, and metadata for secrets, personal data, and third-party rights; rotate any exposed credentials.
- [ ] Run a full maintained secret scanner over history; review results without publishing secret values.
- [ ] Confirm Apache-2.0 licensing, ownership, notices, and all dependency licenses.
- [ ] Enable and verify enforced branch rules, required checks, and owner review at public visibility or on a paid plan.
- [ ] Enable GitHub secret scanning and push protection when eligible; do not claim local pattern matching is equivalent.
- [ ] Establish and test a confidential vulnerability-reporting channel and conduct-reporting/appeal contacts.
- [ ] Verify organization 2FA and access policies, repository and Actions settings, fork workflow approvals, and spending limits.
- [ ] Add language-specific lint/type/test, dependency audit, and code scanning once the implementation stack exists.
- [ ] Publish only demonstrated guarantees, limitations, conformance evidence, and a release/security support policy.

Actual applied settings and blockers belong in SETUP_STATUS.md; this target checklist is not evidence of enforcement.
