import importlib.util
import shutil
import subprocess
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "check_repository", Path(__file__).resolve().parents[1] / "scripts/check_repository.py"
)
CHECK = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECK)
DOC_SPEC = importlib.util.spec_from_file_location(
    "docs_cli", Path(__file__).resolve().parents[1] / "scripts/check_docs.py"
)
DOCS = importlib.util.module_from_spec(DOC_SPEC)
DOC_SPEC.loader.exec_module(DOCS)


@pytest.fixture
def repository(tmp_path):
    git = shutil.which("git")
    for name in CHECK.REQUIRED:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("")
    for workflow in (tmp_path / ".github/workflows").glob("*.yml"):
        workflow.write_text(
            "contents: read\npersist-credentials: false\nuses: actions/checkout@" + "a" * 40 + "\n"
        )
    shutil.copyfile(
        Path(__file__).resolve().parents[1] / ".pymarkdown.json", tmp_path / ".pymarkdown.json"
    )

    def stage(*names):
        subprocess.run([git, "add", "--", *names], cwd=tmp_path, check=True, capture_output=True)  # noqa: S603

    subprocess.run([git, "init", "-q"], cwd=tmp_path, check=True, capture_output=True)  # noqa: S603
    stage(".")
    return tmp_path, stage


def test_hygiene_accepts_source_and_env_example(repository, capsys):
    root, stage = repository
    (root / ".env.example").write_text("VALUE=synthetic\n")
    (root / "removed.py").write_text("")
    stage(".")
    (root / "removed.py").unlink()
    assert CHECK.main(root) == 0
    assert "passed" in capsys.readouterr().out


@pytest.mark.parametrize(
    "name,data,reason",
    [
        (".env", b"VALUE=x", "Environment file"),
        ("secret.pem", b"synthetic", "Sensitive/runtime"),
        ("large.txt", b"x" * 1_000_001, "Large file"),
        ("binary.txt", b"a\0b", "Binary file"),
        ("invalid.txt", b"\xff", "Non-UTF-8"),
        ("secret.txt", ("ghp_" + "x" * 40).encode(), "Possible credential"),
        (".github/workflows/unpinned.yml", b"uses: actions/checkout@main", "full commit SHA"),
        (".github/workflows/privileged.yml", b"pull_request_target:\n", "Privileged PR trigger"),
        (".github/workflows/writable.yml", b"contents: write\n", "read permissions"),
    ],
)
def test_hygiene_rejects_unsafe_tracked_content(repository, capsys, name, data, reason):
    root, stage = repository
    (root / name).write_bytes(data)
    stage(name)
    assert CHECK.main(root) == 1
    output = capsys.readouterr().err
    assert reason in output
    assert "x" * 40 not in output


def test_hygiene_rejects_symlinks_and_missing_required_files(repository):
    root, stage = repository
    (root / "alias").symlink_to(root / "README.md")
    stage("alias")
    (root / "README.md").unlink()
    errors, _ = CHECK.check_repository(root)
    assert any("Symlink" in error for error in errors)
    assert any("Missing required file: README.md" in error for error in errors)


def test_hygiene_requires_git(repository, monkeypatch):
    monkeypatch.setattr(CHECK.shutil, "which", lambda _: None)
    with pytest.raises(RuntimeError, match="Git is required"):
        CHECK.main(repository[0])


@pytest.mark.parametrize(
    "content,expected",
    [
        ("# Good\n", 0),
        ("[missing](missing.md)\n", 1),
        ("#Bad\n", 1),
    ],
)
def test_docs_cli_checks_links_and_markdown_style(repository, content, expected):
    root, _ = repository
    (root / "README.md").write_text(content)
    assert DOCS.main(root) == expected


def test_docs_cli_requires_git(repository, monkeypatch):
    monkeypatch.setattr(DOCS.shutil, "which", lambda _: None)
    with pytest.raises(RuntimeError, match="Git is required"):
        DOCS.main(repository[0])
