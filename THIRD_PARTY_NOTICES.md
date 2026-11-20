# Third-party dependencies

Work Steward's code is licensed under [Apache-2.0](LICENSE). No third-party source is vendored. Dependencies are installed separately with their own licenses; the wheel does not bundle them.

The sole runtime package, [rfc8785](https://pypi.org/project/rfc8785/), uses Apache-2.0. Its distribution supplies its license. Python is provided separately under the Python Software Foundation license.

Development and build tools are not part of the runtime package. Their licenses include MIT, BSD, Apache-2.0, PSF-2.0, MPL-2.0 (Hypothesis and pathspec), and GPL-3.0-or-later (the separate yamllint CLI). Gitleaks is a separately downloaded MIT-licensed CI tool. Keep dependency license files and notices when redistributing those packages or modified third-party code.

[pyproject.toml](pyproject.toml) declares dependencies and build tools; [uv.lock](uv.lock) records resolved development/runtime versions and hashes. Run `make audit` to check the locked environment against current advisories. This is an advisory check, not a guarantee that dependencies are vulnerability-free.
