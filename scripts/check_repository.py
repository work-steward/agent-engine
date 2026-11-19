"""Dependency-free file and workflow hygiene checks."""

import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = (
    "README.md",
    "LICENSE",
    "CONTRIBUTING.md",
    "SECURITY.md",
    ".github/CODEOWNERS",
    ".github/workflows/repository-checks.yml",
    "pyproject.toml",
    "uv.lock",
)


def check_repository(root: Path) -> tuple[list[str], int]:
    errors = []
    for name in REQUIRED:
        if not (root / name).is_file():
            errors.append(f"Missing required file: {name}")

    git = shutil.which("git")
    if git is None:
        raise RuntimeError("Git is required to enumerate repository files")
    # Fixed Git arguments, no shell or user-supplied command text.
    result = subprocess.run(  # noqa: S603
        [git, "ls-files", "-z"],
        cwd=root,
        check=True,
        capture_output=True,
    )
    paths = [root / p for p in result.stdout.decode().split("\0") if p]
    secret_patterns = [
        re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
        re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b"),
        re.compile(r"\bgithub_pat_[A-Za-z0-9_]{40,}\b"),
        re.compile(r"\bAKIA[A-Z0-9]{16}\b"),
    ]
    for path in paths:
        rel = path.relative_to(root).as_posix()
        if not path.exists() and not path.is_symlink():
            continue  # Allow unstaged deletions; required files were checked above.
        if path.is_symlink():
            errors.append(f"Symlink requires explicit policy review: {rel}")
            continue
        if path.name.startswith(".env") and path.name != ".env.example":
            errors.append(f"Environment file tracked: {rel}")
        if path.suffix.lower() in {".pem", ".key", ".p12", ".pfx", ".db", ".sqlite", ".sqlite3"}:
            errors.append(f"Sensitive/runtime file tracked: {rel}")
        data = path.read_bytes()
        if len(data) > 1_000_000:
            errors.append(f"Large file requires explicit policy review: {rel}")
        if b"\x00" in data:
            errors.append(f"Binary file requires explicit policy review: {rel}")
            continue
        try:
            content = data.decode("utf-8")
        except UnicodeDecodeError:
            errors.append(f"Non-UTF-8 file requires explicit policy review: {rel}")
            continue
        if any(pattern.search(content) for pattern in secret_patterns):
            errors.append(f"Possible credential in {rel}; inspect locally (value redacted)")
        if rel.startswith(".github/workflows/"):
            for line in content.splitlines():
                match = re.search(r"\buses:\s*(\S+)", line)
                if match and not re.fullmatch(r"[^\s@]+@[0-9a-f]{40}", match[1]):
                    errors.append(f"Action must be pinned to full commit SHA: {rel}")
            if re.search(r"\bpull_request_target\s*:", content):
                errors.append(f"Privileged PR trigger requires explicit policy review: {rel}")
            if "persist-credentials: false" not in content or "contents: read" not in content:
                errors.append(
                    f"Workflow needs read permissions and no persisted checkout credentials: {rel}"
                )
    return errors, len(paths)


def main(root: Path = ROOT) -> int:
    errors, count = check_repository(root)
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print(f"Repository hygiene passed ({count} tracked files).")
    print("Pattern checks are limited; no runtime or complete secret-scanning guarantee.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
