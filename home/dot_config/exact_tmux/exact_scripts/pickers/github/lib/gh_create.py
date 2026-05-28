#!/usr/bin/env python3
"""Create issues and epics for the GitHub picker.

Stdlib only (no PyGithub, no requests), mirroring `gh_palette_verbs.py`'s
`_run_gh` pattern. The orchestrator (`gh_create.sh`) owns terminal interaction
($EDITOR, fzf prompts); this module owns buffer parsing and `gh` side effects.

Subcommands:
- `create --repo R --kind issue|epic --file BUF [--dry-run]`: create a single
  issue, or an epic (a parent issue plus N child issues linked via the
  sub-issues GraphQL API).
- `repo-candidates --cache-file F`: list distinct repos from the picker cache
  to seed the orchestrator's repo prompt.

Buffer format:
- Lines that are a full-line HTML comment (`<!-- ... -->`) are stripped, so the
  template's instructions never leak into a title or body. `#` lines are kept
  so Markdown headings survive in bodies.
- The first non-empty line of a section is its title; the rest is the body.
- For epics, a line that is exactly `---` separates the parent (first section)
  from each child section.

stdout contract:
- `create` (real): a single `<number>\t<url>` line for the issue / epic parent.
- `create --dry-run`: a JSON object describing what would be created.
- `repo-candidates`: one `owner/repo` per line.

Human-readable progress and errors go to stderr. Exit code is non-zero on fatal
failure (the issue / epic parent could not be created); child-link failures are
reported but do not fail the run once the parent exists.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from typing import List, Sequence, Tuple

_HTML_COMMENT = re.compile(r"^<!--.*-->$")

_ADD_SUB_ISSUE = (
    "mutation($parentId: ID!, $childId: ID!) {"
    " addSubIssue(input: { issueId: $parentId, subIssueId: $childId }) {"
    " subIssue { number } } }"
)


class GhError(Exception):
    """Raised when a `gh` invocation fails in a way that should abort the step."""


def _run_gh(args: Sequence[str], timeout: int = 60) -> Tuple[int, str, str]:
    try:
        proc = subprocess.run(
            ["gh", *args],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return proc.returncode, proc.stdout, proc.stderr
    except FileNotFoundError:
        return 127, "", "gh CLI not found"
    except subprocess.TimeoutExpired:
        return 124, "", "gh CLI timed out"


def _is_instruction_comment(line: str) -> bool:
    return bool(_HTML_COMMENT.match(line.strip()))


def _normalize_lines(text: str) -> List[str]:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return [ln for ln in text.split("\n") if not _is_instruction_comment(ln)]


def _section_title_body(lines: List[str]) -> Tuple[str, str]:
    title_idx = None
    for i, ln in enumerate(lines):
        if ln.strip():
            title_idx = i
            break
    if title_idx is None:
        return "", ""
    title = lines[title_idx].strip()
    body = "\n".join(lines[title_idx + 1 :]).strip()
    return title, body


def parse_issue(text: str) -> Tuple[str, str]:
    """Parse a single-issue buffer into `(title, body)`."""
    return _section_title_body(_normalize_lines(text))


def parse_epic(text: str) -> Tuple[str, str, List[Tuple[str, str]]]:
    """Parse an epic buffer into `(parent_title, parent_body, children)`.

    Sections are split on lines that are exactly `---`. The first non-empty
    section is the parent; the rest are children. Empty sections are dropped.
    """
    sections: List[List[str]] = []
    current: List[str] = []
    for ln in _normalize_lines(text):
        if ln.strip() == "---":
            sections.append(current)
            current = []
        else:
            current.append(ln)
    sections.append(current)

    parsed: List[Tuple[str, str]] = []
    for sec in sections:
        title, body = _section_title_body(sec)
        if title:
            parsed.append((title, body))

    if not parsed:
        return "", "", []
    parent_title, parent_body = parsed[0]
    return parent_title, parent_body, parsed[1:]


def _create_issue(repo: str, title: str, body: str) -> Tuple[int, str, str]:
    """Create one issue via the REST API. Returns `(number, html_url, node_id)`."""
    rc, out, err = _run_gh(
        [
            "api",
            "--method",
            "POST",
            f"repos/{repo}/issues",
            "-f",
            f"title={title}",
            "-f",
            f"body={body}",
        ]
    )
    if rc != 0:
        raise GhError(f"create issue '{title}': {(err or out).strip()}")
    try:
        data = json.loads(out)
    except json.JSONDecodeError as exc:
        raise GhError(f"create issue '{title}': could not parse response") from exc
    number = data.get("number")
    if not number:
        raise GhError(f"create issue '{title}': no number in response")
    return int(number), data.get("html_url", ""), data.get("node_id", "")


def _link_sub_issue(parent_node_id: str, child_node_id: str) -> None:
    """Attach a child issue to its parent via the sub-issues GraphQL mutation."""
    rc, out, err = _run_gh(
        [
            "api",
            "graphql",
            "-H",
            "GraphQL-Features:issue_types",
            "-H",
            "GraphQL-Features:sub_issues",
            "-f",
            f"parentId={parent_node_id}",
            "-f",
            f"childId={child_node_id}",
            "-f",
            f"query={_ADD_SUB_ISSUE}",
        ]
    )
    if rc != 0:
        raise GhError((err or out).strip() or "addSubIssue mutation failed")


def cmd_create(args: argparse.Namespace) -> int:
    try:
        with open(args.file, encoding="utf-8") as fh:
            text = fh.read()
    except OSError as exc:
        print(f"gh_create: cannot read buffer: {exc}", file=sys.stderr)
        return 2

    if args.kind == "issue":
        parent_title, parent_body = parse_issue(text)
        children: List[Tuple[str, str]] = []
    else:
        parent_title, parent_body, children = parse_epic(text)

    if not parent_title:
        label = "issue" if args.kind == "issue" else "epic parent"
        print(f"gh_create: empty {label}; nothing to create", file=sys.stderr)
        return 2

    if args.dry_run:
        plan = {
            "repo": args.repo,
            "kind": args.kind,
            "title": parent_title,
            "body": parent_body,
            "children": [{"title": t, "body": b} for t, b in children],
        }
        print(json.dumps(plan, sort_keys=True))
        return 0

    try:
        parent_num, parent_url, parent_node = _create_issue(args.repo, parent_title, parent_body)
    except GhError as exc:
        print(f"gh_create: {exc}", file=sys.stderr)
        return 1

    print(f"created {args.repo}#{parent_num}: {parent_title}", file=sys.stderr)

    child_fail = 0
    for ctitle, cbody in children:
        try:
            cnum, _curl, cnode = _create_issue(args.repo, ctitle, cbody)
        except GhError as exc:
            print(f"gh_create: child '{ctitle}': {exc}", file=sys.stderr)
            child_fail += 1
            continue
        try:
            _link_sub_issue(parent_node, cnode)
            print(f"  linked #{cnum} as sub-issue of #{parent_num}: {ctitle}", file=sys.stderr)
        except GhError as exc:
            print(f"gh_create: link #{cnum} -> #{parent_num} failed: {exc}", file=sys.stderr)
            child_fail += 1

    if children:
        linked = len(children) - child_fail
        print(f"epic #{parent_num}: {linked}/{len(children)} sub-issues linked", file=sys.stderr)

    # stdout contract: parent/issue identity for the orchestrator's worktree step.
    print(f"{parent_num}\t{parent_url}")
    return 0


def cmd_repo_candidates(args: argparse.Namespace) -> int:
    seen = set()
    ordered: List[str] = []
    try:
        with open(args.cache_file, encoding="utf-8") as fh:
            for line in fh:
                cols = line.rstrip("\n").split("\t")
                if len(cols) < 4:
                    continue
                kind, repo = cols[1], cols[2]
                if kind in ("pr", "issue") and repo and repo not in seen:
                    seen.add(repo)
                    ordered.append(repo)
    except OSError:
        return 0
    for repo in ordered:
        print(repo)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Create issues and epics for the GitHub picker.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("create")
    p.add_argument("--repo", required=True)
    p.add_argument("--kind", required=True, choices=["issue", "epic"])
    p.add_argument("--file", required=True)
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(func=cmd_create)

    p = sub.add_parser("repo-candidates")
    p.add_argument("--cache-file", required=True)
    p.set_defaults(func=cmd_repo_candidates)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
