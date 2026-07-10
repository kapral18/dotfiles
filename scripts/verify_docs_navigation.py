#!/usr/bin/env python3
"""Verify the human-facing docs navigation layer stays wired to real targets.

The Mermaid catalog is machine-checked by ``verify_mermaids.py`` and the comma
command catalog is checked by ``verify_bin_surface.py``. The docs tree is the
human-facing navigation layer for the repo, so this verifier keeps it from
pointing at missing files, missing headings, or stale catalog coverage.

Usage:
    verify_docs_navigation.py [REPO_ROOT]

Exit status is non-zero if:

- no docs Markdown pages are found under ``docs/``
- a relative Markdown link in any docs page points at a missing file/directory
- a relative Markdown link in a docs page points at a missing Markdown heading
- ``implementation-coverage.md`` omits one of the known catalog rows
"""

from __future__ import annotations

import re
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlsplit

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
DOC_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
FENCE_RE = re.compile(r"^(```|~~~)")
INLINE_CODE_RE = re.compile(r"`([^`]*)`")
INLINE_LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]+\)")
HTML_TAG_RE = re.compile(r"<[^>]+>")


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


def _link_fragment(target: str) -> str:
    parsed = urlsplit(target.strip())
    return unquote(parsed.fragment)


def discover_docs(repo_root: Path) -> tuple[Path, ...]:
    """Return every Markdown docs page under ``docs/`` relative to repo root."""

    docs_root = repo_root / "docs"
    if not docs_root.is_dir():
        return tuple()
    return tuple(sorted(path.relative_to(repo_root) for path in docs_root.rglob("*.md")))


def _iter_markdown_links(repo_root: Path, doc_paths: tuple[Path, ...] | None = None) -> list[MarkdownLink]:
    links: list[MarkdownLink] = []
    for rel_path in discover_docs(repo_root) if doc_paths is None else doc_paths:
        path = repo_root / rel_path
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        for match in MARKDOWN_LINK_RE.finditer(text):
            target = match.group(1).strip()
            if not target or _is_external_link(target):
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


def _slugify_heading(text: str) -> str:
    text = INLINE_CODE_RE.sub(r"\1", text)
    text = INLINE_LINK_RE.sub(r"\1", text)
    text = HTML_TAG_RE.sub("", text)
    text = unicodedata.normalize("NFKD", text.casefold())
    text = "".join(char for char in text if not unicodedata.combining(char))
    cleaned = "".join(char if char.isalnum() or char in {" ", "-"} else " " for char in text)
    return re.sub(r"-{2,}", "-", re.sub(r"\s+", "-", cleaned).strip("-"))


def _doc_anchor_ids(repo_root: Path, rel_path: Path) -> set[str]:
    text = (repo_root / rel_path).read_text(encoding="utf-8")
    anchors: set[str] = set()
    seen: dict[str, int] = {}
    in_fence = False
    for line in text.splitlines():
        if FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        match = DOC_HEADING_RE.match(line)
        if not match:
            continue
        slug = _slugify_heading(match.group(2))
        if not slug:
            continue
        duplicate_index = seen.get(slug, 0)
        seen[slug] = duplicate_index + 1
        anchors.add(slug if duplicate_index == 0 else f"{slug}-{duplicate_index}")
    return anchors


def _docs_markdown_target(repo_root: Path, link: MarkdownLink) -> Path | None:
    docs_root = (repo_root / "docs").resolve()
    target_path = (repo_root / link.source).resolve() if not _link_path(link.target) else _resolve_link(repo_root, link)
    if target_path.suffix != ".md" or not target_path.is_file():
        return None
    try:
        target_path.relative_to(docs_root)
    except ValueError:
        return None
    return target_path.relative_to(repo_root.resolve())


def _link_anchor_exists(
    repo_root: Path,
    link: MarkdownLink,
    anchor_cache: dict[Path, set[str]],
) -> bool:
    fragment = _link_fragment(link.target)
    if not fragment:
        return True
    target_doc = _docs_markdown_target(repo_root, link)
    if target_doc is None:
        return True
    anchors = anchor_cache.setdefault(target_doc, _doc_anchor_ids(repo_root, target_doc))
    return fragment in anchors


def check_links(repo_root: Path, doc_paths: tuple[Path, ...] | None = None) -> list[str]:
    """Return failures for broken relative Markdown links and anchors in docs pages."""

    failures: list[str] = []
    checked_docs = discover_docs(repo_root) if doc_paths is None else doc_paths
    for rel_path in checked_docs:
        if not (repo_root / rel_path).is_file():
            failures.append(f"docs navigation page missing: {rel_path}")

    anchor_cache: dict[Path, set[str]] = {}
    for link in _iter_markdown_links(repo_root, checked_docs):
        if not _link_exists(repo_root, link):
            failures.append(f"{link.source}: broken link target {link.target}")
            continue
        if not _link_anchor_exists(repo_root, link, anchor_cache):
            failures.append(f"{link.source}: broken anchor target {link.target}")
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

    discovered_docs = discover_docs(repo_root)
    failures: list[str] = []
    if not discovered_docs:
        failures.append("docs navigation verification failed: no Markdown pages found under docs/")
    return [
        *failures,
        *check_links(repo_root, discovered_docs),
        *check_catalog_rows(repo_root),
        *check_reference_map_scripts(repo_root),
    ]


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) > 1:
        print("Usage: verify_docs_navigation.py [REPO_ROOT]", file=sys.stderr)
        return 2

    repo_root = Path(args[0]).expanduser().resolve() if args else Path(__file__).resolve().parent.parent
    if not (repo_root / "docs").is_dir():
        print(f"docs/ not found under {repo_root}", file=sys.stderr)
        return 2

    discovered_docs = discover_docs(repo_root)
    failures = check_docs_navigation(repo_root)
    if failures:
        print(f"docs navigation verification failed ({len(failures)} issue(s)):", file=sys.stderr)
        for failure in failures:
            print(f"  ✗ {failure}", file=sys.stderr)
        return 1

    print(
        f"docs navigation verification passed ({len(discovered_docs)} pages, {len(EXPECTED_CATALOG_ROWS)} catalog rows)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
