"""Lint Markdown structure and local links without fetching external URLs."""

import posixpath
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

from markdown_it import MarkdownIt
from markdown_it.token import Token


def link_targets(tokens: list[Token]):
    for token in tokens:
        if token.type in ("link_open", "image"):
            yield token.attrGet("href" if token.type == "link_open" else "src")
        if token.children:
            yield from link_targets(token.children)


def check_links(root: Path, files: list[Path]) -> list[str]:
    root = root.resolve()
    # Ignore deleted paths and never follow a source symlink into a private file.
    files = [path for path in files if (root / path).is_file() and not (root / path).is_symlink()]
    known = {path.as_posix() for path in files}
    errors = []
    parser = MarkdownIt("commonmark")
    # Inspect even unsafe URI schemes as lint input; this parser never renders or opens them.
    parser.validateLink = lambda _href: True
    for path in files:
        if path.suffix != ".md":
            continue
        try:
            tokens = parser.parse((root / path).read_text(encoding="utf-8"))
        except (UnicodeError, OSError):
            errors.append(f"{path}: cannot read UTF-8 Markdown")
            continue
        for href in link_targets(tokens):
            try:
                target = urlsplit(href)
                if target.scheme in {"http", "https", "mailto"} or (
                    not target.scheme and target.netloc
                ):
                    continue
                if target.scheme:
                    raise ValueError("unsupported link scheme")
                if not target.path:
                    continue  # Heading anchors are handled by the Markdown linter.
                decoded = unquote(target.path, encoding="utf-8", errors="strict")
                if decoded.startswith("/"):
                    raise ValueError("use a relative repository path")
                relative = posixpath.normpath((path.parent / decoded).as_posix())
                if relative == ".." or relative.startswith("../"):
                    raise ValueError("target is outside the repository")
                resolved = (root / relative).resolve()
                resolved.relative_to(root)
                if relative not in known and not (
                    resolved.is_dir()
                    and any(relative == "." or name.startswith(relative + "/") for name in known)
                ):
                    raise ValueError("target is missing or not a repository file")
            except (ValueError, OSError) as exc:
                errors.append(f"{path}: {href}: {exc}")
    return errors


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    git = shutil.which("git")
    if git is None:
        raise RuntimeError("Git is required to enumerate repository files")
    # Fixed Git arguments, no shell and no arguments derived from Markdown.
    result = subprocess.run(  # noqa: S603
        [git, "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=root,
        check=True,
        capture_output=True,
    )
    files = [Path(name) for name in result.stdout.decode().split("\0") if name]
    markdown = [
        str(root / path)
        for path in files
        if path.suffix == ".md" and (root / path).is_file() and not (root / path).is_symlink()
    ]
    # Repository paths are absolute arguments to the pinned linter module, never shell commands.
    style = subprocess.run(  # noqa: S603
        [
            sys.executable,
            "-m",
            "pymarkdown",
            "--config",
            str(root / ".pymarkdown.json"),
            "--strict-config",
            "scan",
            *markdown,
        ],
        cwd=root,
        check=False,
    )
    errors = check_links(root, files)
    if errors:
        print("\n".join(errors))
        return 1
    print("Local Markdown links resolve; external URLs were not fetched.")
    return 1 if style.returncode else 0


if __name__ == "__main__":
    raise SystemExit(main())
