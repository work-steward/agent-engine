# Contributing

Start with the README, architecture baseline, and roadmap. Discuss substantial changes in an issue before implementation. Keep pull requests small and independently reviewable.

## Submission and review

- Use a topic branch and pull request targeting `main`; explain the behavior, rationale, and validation.
- Run `python3 scripts/check_repository.py` and `git diff --check` before submission.
- Add meaningful regression, property, crash, or concurrency tests when implementation changes warrant them. Documentation-only changes do not demonstrate execution guarantees.
- A maintainer reviews every external contribution. Changes to authorization, dispatch, persistence, evidence, credentials, workflows, or release controls require explicit review by the relevant owner.
- Preserve the 100 confirmed decisions. Proposed amendments require the project lead's explicit approval and an ADR referencing affected decisions and invariants.
- Separate designed, implemented, tested, and provider-dependent claims. Never reinterpret timeout as definitive remote failure.
- AI assistance is welcome. Contributors remain accountable for correctness, provenance, license compatibility, and verification; disclose substantial assistance in the PR.
- Never submit credentials, private customer data, real business records, or copied material without permission. Use synthetic fixtures. Report vulnerabilities privately under SECURITY.md.

## Rights and licensing

Submit only work you have the right to contribute. Intentionally submitted contributions are under Apache-2.0, as described in that license's contribution terms. Preserve third-party notices and identify new dependencies and their licenses. No separate CLA or mandatory sign-off is configured in this bootstrap.

## Merge policy

Prefer squash merges and delete merged topic branches. Required checks and reviews must pass where GitHub enforcement is available. While private on GitHub Free, these are maintainer procedures, not enforced branch restrictions. The project lead may merge their own changes after documenting self-review; a sole maintainer cannot provide an independent approval of their own PR. Independent review of critical execution changes is a release gate.
