# Setup status — 2026-11-19

Organization: https://github.com/work-steward

Repository: https://github.com/work-steward/agent-engine

## Applied and verified

- GitHub Free organization created; repository private with `main` as default branch.
- Organization default member repository access set to None; member repository creation and private forking disabled.
- Organization Actions limited to the single selected repository `agent-engine`; full-length action commit SHA pinning required. Verified in Safari after API permission limits blocked organization Actions administration.
- Organization default workflow permissions verified read-only, with workflow-created/approved PRs disabled.
- No additional members, collaborators, apps, credentials, or deployment secrets added.
- Private forking disabled by the organization; repository confirms `allow_forking=false`.
- Only squash merges allowed; automatic deletion of merged branches enabled.
- Unused repository wiki and Projects disabled.
- Actions restricted to GitHub-owned actions; verified and arbitrary third-party actions disabled.
- Default Actions token read-only; workflows cannot approve pull requests.
- Dependabot vulnerability alerts and automated security fixes enabled.
- Weekly GitHub Actions dependency update configuration committed.
- Architecture handoff preserved with trailing whitespace normalized; no product decisions amended.
- Apache-2.0 license, governance, contribution rules, CODEOWNERS, security policy, conduct rules, templates, roadmap, and release checklist committed.
- Local repository hygiene and whitespace checks passed. First remote `Repository checks` run passed on bootstrap commit `08c8713c86f6830a2ef46fd3c04acfd17a10fb5f`.

## Limitations and remaining gates

- GitHub returned HTTP 403 when branch protection was requested: upgrade or public visibility is required. Required checks/reviews, force-push and deletion restrictions, and enforced CODEOWNERS review are **not active**. Follow CONTRIBUTING.md procedurally while private on Free.
- Native private-repository secret scanning/push protection and code scanning are not enabled. Bootstrap credential-pattern checks are limited; conduct a maintained full-history scan before public release.
- Organization-required 2FA is not yet enabled. Verify the owner's authentication setup and enable this requirement before adding collaborators. There is only one organization member, the owner.
- A tested private security-reporting channel and independent conduct appeal contact remain public-launch gates.
- The existing Git credential helper was used for upload and API administration. The connected GitHub App cannot yet access this new organization/repository; no new app access was granted.
- No implementation language or storage engine selected. No runtime, simulator, or execution invariants implemented or tested.

See docs/REPOSITORY_SECURITY.md for target controls and public-release requirements. Making the repository public requires a separate owner decision.
