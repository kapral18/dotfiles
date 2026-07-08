#!/usr/bin/env python3
"""Verify the human-facing docs navigation layer stays wired to real targets.

The Mermaid catalog is machine-checked by ``verify_mermaids.py`` and the comma
command catalog is checked by ``verify_bin_surface.py``. The docs/reference
pages are the narrative bridge humans and agents use to find implementation
surfaces, so this verifier keeps that bridge from pointing at missing files or
dropping catalog rows.

Usage:
    verify_docs_navigation.py [REPO_ROOT]

Exit status is non-zero if:

- a checked reference page is missing
- a relative Markdown link in those pages points at a missing file/directory
- ``implementation-coverage.md`` omits one of the known catalog rows
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlsplit

CHECKED_DOCS = (
    Path("docs/reference/reference-map.md"),
    Path("docs/reference/implementation-coverage.md"),
)

EXPECTED_CATALOG_ROWS = (
    "01",
    "02",
    "03",
    "03b",
    "04",
    "04b",
    "05",
    "06",
    "07",
    "07b",
    "07c",
    "08",
    "09",
    "10",
    "11",
    "12",
    "13",
)

MARKDOWN_LINK_RE = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")
CATALOG_ROW_RE = re.compile(r"^\|\s*`([^`]+)`\s*\|", re.MULTILINE)
SECTION_HEADING_RE = re.compile(r"^## ", re.MULTILINE)


@dataclass(frozen=True)
class MarkdownLink:
    """A relative Markdown link found in a checked docs page."""

    source: Path
    target: str


def _is_external_link(target: str) -> bool:
    parsed = urlsplit(target)
    return bool(parsed.scheme or parsed.netloc)


def _link_path(target: str) -> str:
    parsed = urlsplit(target.strip())
    return unquote(parsed.path)


def _iter_markdown_links(repo_root: Path, doc_paths: tuple[Path, ...] = CHECKED_DOCS) -> list[MarkdownLink]:
    links: list[MarkdownLink] = []
    for rel_path in doc_paths:
        path = repo_root / rel_path
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        for match in MARKDOWN_LINK_RE.finditer(text):
            target = match.group(1).strip()
            if not target or target.startswith("#") or _is_external_link(target):
                continue
            links.append(MarkdownLink(source=rel_path, target=target))
    return links


def _resolve_link(repo_root: Path, link: MarkdownLink) -> Path:
    path_part = _link_path(link.target)
    return (repo_root / link.source.parent / path_part).resolve()


def _link_exists(repo_root: Path, link: MarkdownLink) -> bool:
    path_part = _link_path(link.target)
    if not path_part:
        return True
    target_path = _resolve_link(repo_root, link)
    try:
        target_path.relative_to(repo_root.resolve())
    except ValueError:
        return False
    return target_path.exists() or target_path.is_symlink()


def check_links(repo_root: Path, doc_paths: tuple[Path, ...] = CHECKED_DOCS) -> list[str]:
    """Return failures for broken relative Markdown links in checked docs."""

    failures: list[str] = []
    for rel_path in doc_paths:
        if not (repo_root / rel_path).is_file():
            failures.append(f"docs navigation page missing: {rel_path}")

    for link in _iter_markdown_links(repo_root, doc_paths):
        if not _link_exists(repo_root, link):
            failures.append(f"{link.source}: broken link target {link.target}")
    return failures


def _catalog_rows(repo_root: Path) -> set[str]:
    path = repo_root / "docs/reference/implementation-coverage.md"
    if not path.is_file():
        return set()
    text = path.read_text(encoding="utf-8")
    return set(CATALOG_ROW_RE.findall(text))


def check_catalog_rows(repo_root: Path, expected: tuple[str, ...] = EXPECTED_CATALOG_ROWS) -> list[str]:
    """Return failures for missing implementation-coverage catalog rows."""

    actual = _catalog_rows(repo_root)
    failures: list[str] = []
    for row in expected:
        if row not in actual:
            failures.append(f"docs/reference/implementation-coverage.md: missing catalog row `{row}`")
    return failures


def _section_after_heading(text: str, heading: str) -> str:
    start = text.find(heading)
    if start == -1:
        return ""
    next_heading = SECTION_HEADING_RE.search(text, start + len(heading))
    return text[start : next_heading.start()] if next_heading else text[start:]


def check_reference_map_scripts(repo_root: Path) -> list[str]:
    """Return failures for stale ``scripts/`` entries in the reference map."""

    path = repo_root / "docs/reference/reference-map.md"
    if not path.is_file():
        return []

    text = path.read_text(encoding="utf-8")
    section = _section_after_heading(text, "## Scripts (`scripts/`)")
    if not section:
        return ["docs/reference/reference-map.md: missing Scripts (`scripts/`) section"]

    failures: list[str] = []
    for entry in CATALOG_ROW_RE.findall(section):
        script_path = repo_root / "scripts" / entry.rstrip("/")
        if not script_path.exists():
            failures.append(f"docs/reference/reference-map.md: missing scripts/{entry} referenced in Scripts table")
    return failures


def check_docs_navigation(repo_root: Path) -> list[str]:
    """Return human-readable docs navigation failures."""

    return [*check_links(repo_root), *check_catalog_rows(repo_root), *check_reference_map_scripts(repo_root)]


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) > 1:
        print("Usage: verify_docs_navigation.py [REPO_ROOT]", file=sys.stderr)
        return 2

    repo_root = Path(args[0]).expanduser().resolve() if args else Path(__file__).resolve().parent.parent
    if not (repo_root / "docs" / "reference").is_dir():
        print(f"docs/reference not found under {repo_root}", file=sys.stderr)
        return 2

    failures = check_docs_navigation(repo_root)
    if failures:
        print(f"docs navigation verification failed ({len(failures)} issue(s)):", file=sys.stderr)
        for failure in failures:
            print(f"  ✗ {failure}", file=sys.stderr)
        return 1

    print(f"docs navigation verification passed ({len(CHECKED_DOCS)} pages, {len(EXPECTED_CATALOG_ROWS)} catalog rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
