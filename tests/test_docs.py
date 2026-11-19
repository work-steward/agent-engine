"""Regression cases for repository link checking, including Markdown parsing and path scope."""

import importlib.util
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "check_docs", Path(__file__).resolve().parents[1] / "scripts/check_docs.py"
)
CHECK_DOCS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECK_DOCS)


def test_markdown_parser_handles_references_images_spaces_and_code_examples(tmp_path):
    (tmp_path / "README.md").write_text(
        "[guide][ref]\n\n[ref]: <a guide.md>\n\n![asset](asset.svg)\n"
        "\n```md\n[example](missing.md)\n```\n\n`[example](also-missing.md)`\n"
        "\n[web](https://example.com) [mail](mailto:maintainer@example.com) [heading](#title)\n"
    )
    (tmp_path / "a guide.md").write_text("# Guide\n")
    (tmp_path / "asset.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg"/>\n')
    files = [Path("README.md"), Path("a guide.md"), Path("asset.svg")]
    assert CHECK_DOCS.check_links(tmp_path, files) == []


@pytest.mark.parametrize(
    "target",
    [
        "missing.md",
        "../outside.md",
        "/private/file.md",
        "file:///private/file.md",
        "exists-but-untracked.md",
        "guide%FF.md",
        "Guide.md",
    ],
)
def test_links_reject_missing_untracked_escaping_and_mis_cased_targets(tmp_path, target):
    (tmp_path / "README.md").write_text(f"[link]({target})\n")
    (tmp_path / "guide.md").write_text("# Guide\n")
    (tmp_path / "exists-but-untracked.md").write_text("# Untracked\n")
    assert CHECK_DOCS.check_links(tmp_path, [Path("README.md"), Path("guide.md")])


def test_directory_links_need_repository_content_and_support_parent_paths(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "empty").mkdir()
    (tmp_path / "README.md").write_text("[docs](docs) [root](.)\n")
    (tmp_path / "docs/guide.md").write_text("[readme](../README.md#title)\n")
    files = [Path("README.md"), Path("docs/guide.md")]
    assert CHECK_DOCS.check_links(tmp_path, files) == []
    (tmp_path / "README.md").write_text("[empty](empty)\n")
    assert CHECK_DOCS.check_links(tmp_path, files)


def test_an_untracked_symlink_cannot_make_a_missing_repository_path_resolve(tmp_path):
    (tmp_path / "README.md").write_text("[alias](alias/guide.md)\n")
    (tmp_path / "guide.md").write_text("# Guide\n")
    (tmp_path / "alias").symlink_to(tmp_path, target_is_directory=True)
    assert CHECK_DOCS.check_links(tmp_path, [Path("README.md"), Path("guide.md")])


def test_non_utf8_markdown_is_rejected_without_reading_symlink_sources(tmp_path):
    (tmp_path / "bad.md").write_bytes(b"\xff")
    (tmp_path / "alias.md").symlink_to(tmp_path / "bad.md")
    errors = CHECK_DOCS.check_links(tmp_path, [Path("bad.md"), Path("alias.md"), Path("gone.md")])
    assert errors == ["bad.md: cannot read UTF-8 Markdown"]
