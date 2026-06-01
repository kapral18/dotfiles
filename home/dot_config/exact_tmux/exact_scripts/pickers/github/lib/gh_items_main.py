#!/usr/bin/env python3
"""Fetch GitHub PRs/issues from gh-picker config sections via GitHub Search API.

Outputs TSV rows suitable for fzf consumption in the GitHub picker.
Uses concurrent fetching for all sections in parallel.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import re
import shlex
import signal
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HALF_CORES = max(1, (os.cpu_count() or 2) // 2)
# I/O-bound work (gh subprocess + network) does not benefit from a CPU-tied
# cap. Pick a generous fan-out that lets every section/repo issue its own
# request in one round-trip; capped to avoid hammering the API on large configs.
IO_FANOUT_CAP = 32

signal.signal(signal.SIGPIPE, signal.SIG_DFL)

RESET = "\033[0m"


def c(code: str, text: str) -> str:
    return f"\033[{code}m{text}{RESET}"


# Nerd Font Octicons (matches session picker + docs)
ICON_PR_OPEN = c("38;5;42", "\uf407")
ICON_PR_MERGED = c("38;5;141", "\uf407")
ICON_PR_CLOSED = c("38;5;196", "\uf4dc")
ICON_PR_DRAFT = c("38;5;242", "\uf407")
ICON_ISSUE_OPEN = c("38;5;42", "\uf41b")
ICON_ISSUE_CLOSED = c("38;5;141", "\uf41d")
ICON_ISSUE_NOT_PLANNED = c("38;5;244", "\uf41d")
# Tree-parent icons. Used by `format_lines` when `_tree_role=parent` so the
# row visually anchors the family beneath it. The leaf icons above keep
# representing item state (open/merged/closed); these only replace the
# leading glyph when a row is the root of a family.
ICON_EPIC = c("38;5;141", "⬢")
ICON_PR_FAMILY = c("38;5;81", "◇")
SECTION_SEP = c("2;38;5;244", "─" * 60)


def relative_date(iso: str) -> str:
    if not iso:
        return ""
    try:
        date_str = iso.split("T")[0]
        then = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        diff = (now - then).days
        if diff == 0:
            return "today"
        if diff == 1:
            return "1d"
        if diff < 7:
            return f"{diff}d"
        if diff < 30:
            return f"{diff // 7}w"
        if diff < 365:
            return f"{diff // 30}mo"
        return f"{diff // 365}y"
    except Exception:
        return iso[:10] if len(iso) >= 10 else iso


def short_repo(nwo: str) -> str:
    return nwo.split("/", 1)[-1] if "/" in nwo else nwo


def resolve_repo_path(nwo: str, repo_paths: dict[str, str]) -> str | None:
    """Resolve a repo (owner/name) to a local path using gh-dash repoPaths patterns."""
    if nwo in repo_paths:
        return os.path.expanduser(repo_paths[nwo])

    owner, name = nwo.split("/", 1) if "/" in nwo else ("", nwo)
    for pattern, path_tmpl in repo_paths.items():
        if pattern == nwo:
            continue
        pat_owner, pat_name = pattern.split("/", 1) if "/" in pattern else ("", pattern)
        if pat_owner in (owner, ":owner", "*") and pat_name in (name, ":repo", "*"):
            result = path_tmpl
            result = result.replace(":owner", owner).replace(":repo", name).replace("*", name)
            return os.path.expanduser(result)
    return None


_ISSUE_SUFFIX_RE = re.compile(r"[-/](\d+)$")


def _find_git_dir(repo_path: str) -> str | None:
    """Find a usable git working directory under repo_path."""
    for candidate in [repo_path, os.path.join(repo_path, "main")]:
        if os.path.isdir(candidate) and (
            os.path.exists(os.path.join(candidate, ".git")) or os.path.exists(os.path.join(candidate, "HEAD"))
        ):
            return candidate
    return None


def _git_worktree_entries(repo_path: str) -> list[tuple[str, str]]:
    """Return (worktree_path, branch) pairs from git worktree list --porcelain."""
    git_dir = _find_git_dir(repo_path)
    if not git_dir:
        return []
    try:
        result = subprocess.run(
            ["git", "-C", git_dir, "worktree", "list", "--porcelain"],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except Exception:
        return []

    entries: list[tuple[str, str]] = []
    wt_path = ""
    branch = ""
    for line in result.stdout.splitlines():
        if line.startswith("worktree "):
            if wt_path and branch:
                entries.append((wt_path, branch))
            wt_path = line.split(" ", 1)[1]
            branch = ""
        elif line.startswith("branch refs/heads/"):
            branch = line.split("refs/heads/", 1)[1]
        elif line == "":
            if wt_path and branch:
                entries.append((wt_path, branch))
            wt_path = ""
            branch = ""
    if wt_path and branch:
        entries.append((wt_path, branch))
    return entries


def _wt_issue_number(wt_path: str) -> str:
    """Read issue number from worktree-local git config (comma.w.issue.number).

    Set by `,w issue` when creating worktrees linked to issues. Zero-cost local lookup.
    """
    try:
        r = subprocess.run(
            ["git", "-C", wt_path, "config", "--worktree", "--get", "comma.w.issue.number"],
            check=False,
            capture_output=True,
            text=True,
            timeout=3,
        )
        return r.stdout.strip() if r.returncode == 0 else ""
    except Exception:
        return ""


class _ItemInfo:
    __slots__ = ("has_wt", "review", "ci", "mergeable")

    def __init__(self, has_wt: bool = False, review: str = "", ci: str = "", mergeable: str = ""):
        self.has_wt = has_wt
        self.review = review
        self.ci = ci
        self.mergeable = mergeable


def _scan_local_worktrees(nwo: str, repo_path: str) -> tuple[set[int], set[str], dict[int, str]]:
    """Collect issue/PR numbers and branch names from local worktrees (no network).

    Returns (wt_nums, branches, branch_num_source) where wt_nums are numbers
    detected via metadata or branch name heuristics, branches are all local
    worktree branch names, and branch_num_source maps numbers extracted from
    branch names to the branch they came from (so callers can detect false
    positives when a branch is claimed by a different PR via GraphQL).
    """
    entries = _git_worktree_entries(repo_path)
    branches: set[str] = set()
    wt_nums: set[int] = set()
    branch_num_source: dict[int, str] = {}

    for wt_path, branch in entries:
        meta_num = _wt_issue_number(wt_path)
        if meta_num:
            try:
                wt_nums.add(int(meta_num))
            except ValueError:
                pass

        m = _ISSUE_SUFFIX_RE.search(branch)
        if m:
            num = int(m.group(1))
            wt_nums.add(num)
            branch_num_source[num] = branch

        branches.add(branch)

    return wt_nums, branches, branch_num_source


_GITHUB_ISSUE_URL_RE = re.compile(r"https?://github\.com/([^/]+/[^/]+)/issues/(\d+)\b")


def _pick_session_cache_paths() -> list[str]:
    cache_home = os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache")
    base = os.path.join(cache_home, "tmux")
    return [
        os.path.join(base, "pick_session_items_ordered.tsv"),
        os.path.join(base, "pick_session_items.tsv"),
    ]


def _linked_issue_numbers_from_pick_session_cache() -> dict[str, set[int]]:
    """Best-effort: map repo NWO -> issue numbers from session/worktree cache.

    This lets the GitHub picker show the local-worktree marker for issues that
    are already linked to an existing session/worktree entry (e.g. via PR
    closing issues references), even if the worktree itself doesn't encode the
    issue number in its branch name or metadata.
    """
    paths = [p for p in _pick_session_cache_paths() if os.path.isfile(p)]
    if not paths:
        return {}

    out: dict[str, set[int]] = {}
    for p in paths:
        try:
            raw = Path(p).read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue

        for line in raw.splitlines():
            if "\t" not in line:
                continue
            parts = line.split("\t")
            if len(parts) < 4:
                continue
            kind = parts[1]
            # Only trust session/worktree rows where meta is present.
            if kind not in ("session", "worktree"):
                continue
            meta = parts[3]
            if "|issue=" not in meta:
                continue

            for m in _GITHUB_ISSUE_URL_RE.finditer(meta):
                nwo, num_s = m.group(1), m.group(2)
                try:
                    num = int(num_s)
                except ValueError:
                    continue
                out.setdefault(nwo, set()).add(num)

        # Prefer ordered snapshot when available (first path in list).
        if p.endswith("pick_session_items_ordered.tsv") and out:
            break

    return out


_TRIVIAL_STATUS_RE = re.compile(
    r"^(CLA|prbot:|renovate/|license/|security/|buildkite/docs)",
    re.IGNORECASE,
)
_TRIVIAL_CHECK_RE = re.compile(
    r"^(Analyze new dependencies|docs-preview)",
    re.IGNORECASE,
)


def _is_trivial_ctx(ctx: dict[str, Any]) -> bool:
    """True if a rollup context is a non-CI/bot check we ignore for badge state.

    Trivial contexts (CLA, prbot:*, renovate, license, docs previews, etc.) can
    fail without the PR's real CI being red. They must be excluded both from the
    aggregate fallback AND from the early "rollup is failing" short-circuit;
    otherwise a single failing trivial check (e.g. `prbot:outdated`) masks a
    green canonical CI context and the picker shows a false failure badge.
    """
    typename = ctx.get("__typename", "")
    name = ctx.get("context", "") or ctx.get("name", "")
    if typename == "StatusContext" and _TRIVIAL_STATUS_RE.search(name):
        return True
    if typename == "CheckRun" and _TRIVIAL_CHECK_RE.search(name):
        return True
    return False


def _ctx_is_failing(ctx: dict[str, Any]) -> bool:
    """True if a single rollup context is in a failing terminal state."""
    if ctx.get("__typename") == "StatusContext":
        return (ctx.get("state") or "").upper() in ("FAILURE", "ERROR")
    if ctx.get("__typename") == "CheckRun":
        return (ctx.get("conclusion") or "").upper() in ("FAILURE", "TIMED_OUT", "CANCELLED")
    return False


def _extract_ci_state(commit_node: dict[str, Any], repo_name: str) -> str:
    """Extract meaningful CI state from status check contexts.

    Priority:
    1. StatusContext named '{repo_name}-ci' (e.g. 'kibana-ci')
    2. Buildkite StatusContext for the repo (excluding docs)
    3. CheckRun whose name contains the repo name (excluding docs)
    4. Aggregate state of non-trivial checks (excludes bots/CLA/docs/snyk)
    5. Empty string if only trivial contexts exist (no real CI ran)
    """
    try:
        rollup = commit_node["statusCheckRollup"]
    except (KeyError, TypeError):
        return ""
    if rollup is None:
        return ""

    contexts = []
    try:
        contexts = (rollup.get("contexts") or {}).get("nodes") or []
    except (AttributeError, TypeError):
        pass

    overall_state = (rollup.get("state") or "").upper()
    if not contexts:
        # No per-context detail to reason about; trust the aggregate, but don't
        # invent a failure from a state we can't attribute to a real check.
        return overall_state if overall_state != "ERROR" else "FAILURE"

    # Never show green when a *real* (non-trivial) check is failing. This still
    # prevents a single canonical success context (e.g. kibana-ci) from masking
    # other failing required checks, but a failing trivial context (CLA,
    # prbot:*, renovate, docs preview) no longer fabricates a red badge.
    if overall_state in ("FAILURE", "ERROR") and any(
        _ctx_is_failing(ctx) and not _is_trivial_ctx(ctx) for ctx in contexts
    ):
        return "FAILURE"

    canonical = f"{repo_name}-ci"
    for ctx in contexts:
        if ctx.get("__typename") == "StatusContext" and ctx.get("context") == canonical:
            return ctx.get("state", "")

    for ctx in contexts:
        if ctx.get("__typename") != "StatusContext":
            continue
        name = ctx.get("context", "")
        if name.startswith("buildkite/") and repo_name in name and "docs" not in name:
            return ctx.get("state", "")

    for ctx in contexts:
        if ctx.get("__typename") != "CheckRun":
            continue
        name = ctx.get("name", "")
        if repo_name in name.lower() and "docs" not in name.lower():
            conclusion = ctx.get("conclusion", "")
            status = ctx.get("status", "")
            if conclusion == "SUCCESS":
                return "SUCCESS"
            if conclusion in ("FAILURE", "TIMED_OUT", "CANCELLED"):
                return "FAILURE"
            if status in ("IN_PROGRESS", "QUEUED", "WAITING"):
                return "PENDING"

    has_failure = False
    has_pending = False
    has_success = False
    real_count = 0
    for ctx in contexts:
        typename = ctx.get("__typename", "")
        if _is_trivial_ctx(ctx):
            continue
        real_count += 1
        if typename == "StatusContext":
            st = (ctx.get("state") or "").upper()
            if st == "FAILURE":
                has_failure = True
            elif st == "PENDING":
                has_pending = True
            elif st == "SUCCESS":
                has_success = True
        elif typename == "CheckRun":
            conclusion = (ctx.get("conclusion") or "").upper()
            status = (ctx.get("status") or "").upper()
            if conclusion in ("FAILURE", "TIMED_OUT", "CANCELLED"):
                has_failure = True
            elif conclusion == "SUCCESS":
                has_success = True
            elif status in ("IN_PROGRESS", "QUEUED", "WAITING"):
                has_pending = True

    if real_count == 0:
        return ""
    if has_failure:
        return "FAILURE"
    if has_pending:
        return "PENDING"
    if has_success:
        return "SUCCESS"
    return ""


_PR_METADATA_CHUNK = 5

# Tuple layout returned by `_graphql_pr_metadata_chunk`. Kept as a positional
# tuple (rather than a NamedTuple) because the downstream unpacking site in
# `main` is a tight loop; positional access is one less attribute lookup.
# Indices: 0=headRefName, 1=reviewDecision, 2=ciState, 3=mergeable,
#          4=title, 5=body, 6=baseRefName,
#          7=closing_issues (list[(repo, num, state)], optional).
#
# `_PR_META_LEN` covers fields 0..6 which every backport-grouping path needs.
# `_PR_META_CLOSES` is checked explicitly at its single consumer because the
# trailing closing-issues field was added later and is optional in synthetic
# test fixtures.
_PR_META_LEN = 7
_PR_META_TITLE = 4
_PR_META_BODY = 5
_PR_META_BASE = 6
_PR_META_CLOSES = 7

# Cap GraphQL `closingIssuesReferences` / `closedByPullRequestsReferences`
# fetches to a small first-N. The picker only ever displays one badge per
# row; deeper history goes through the preview pane. Five is plenty of head-
# room for the rare "1 PR closes 3 issues" case while keeping the GraphQL
# alias size flat.
_CROSS_LINK_FETCH_LIMIT = 5


def _graphql_pr_metadata_chunk(items: list[tuple[str, int]]) -> dict[str, dict[int, tuple]]:
    """Fetch metadata for a small batch of (nwo, number) pairs.

    Kept tight (≈5 PRs) because GitHub GraphQL evaluates aliases mostly
    serially per request: many small parallel calls beat one large batch.

    Per PR we fetch:
      - `headRefName` / `baseRefName` for backport-family branch detection
      - `reviewDecision` / `mergeable` / CI rollup for badges
      - `title` / `body` for backport-family title+body detection
      - `closingIssuesReferences` (first 5) for PR \u2194 Issue cross-linking
    """
    aliases: list[str] = []
    alias_map: dict[str, tuple[str, int]] = {}
    for nwo, n in items:
        owner, name = nwo.split("/", 1) if "/" in nwo else ("", nwo)
        alias = f"_p{owner}_{name}_{n}".replace("-", "_")
        aliases.append(
            f'{alias}: repository(owner: "{owner}", name: "{name}") '
            f"{{ pullRequest(number: {n}) {{ number headRefName baseRefName title body "
            f"reviewDecision mergeable "
            f"closingIssuesReferences(first: {_CROSS_LINK_FETCH_LIMIT}) {{ nodes {{ "
            f"number state repository {{ nameWithOwner }} }} }} "
            f"commits(last:1) {{ nodes {{ commit {{ statusCheckRollup {{ state "
            f"contexts(first:100) {{ nodes {{ "
            f"... on CheckRun {{ __typename name conclusion status }} "
            f"... on StatusContext {{ __typename context state }} "
            f"}} }} }} }} }} }} }} }}"
        )
        alias_map[alias] = (nwo, n)

    if not aliases:
        return {}

    query = "query { " + " ".join(aliases) + " }"
    try:
        result = subprocess.run(
            ["gh", "api", "graphql", "-f", f"query={query}"],
            check=False,
            capture_output=True,
            text=True,
            timeout=20,
        )
        if not result.stdout.strip():
            return {}
        data = json.loads(result.stdout).get("data", {})
    except Exception:
        return {}

    out: dict[str, dict[int, tuple]] = {}
    for alias, (nwo, num) in alias_map.items():
        node = (data.get(alias) or {}).get("pullRequest")
        if not node:
            continue
        head = node.get("headRefName", "") or ""
        base = node.get("baseRefName", "") or ""
        title = node.get("title", "") or ""
        body = node.get("body", "") or ""
        review = node.get("reviewDecision", "") or ""
        mergeable = node.get("mergeable", "") or ""
        # GitHub often returns UNKNOWN transiently while computing mergeability.
        # Treat it as missing so we preserve last-known state instead of clearing
        # conflict indicators spuriously.
        if mergeable == "UNKNOWN":
            mergeable = ""
        repo_name = nwo.split("/", 1)[-1] if "/" in nwo else nwo
        ci_state = ""
        try:
            commit = node["commits"]["nodes"][0]["commit"]
            ci_state = _extract_ci_state(commit, repo_name)
        except (KeyError, IndexError, TypeError):
            pass
        closing: list[tuple[str, int, str]] = []
        try:
            for ref in (node.get("closingIssuesReferences") or {}).get("nodes") or []:
                if not ref:
                    continue
                ref_repo = ((ref.get("repository") or {}).get("nameWithOwner")) or nwo
                try:
                    ref_num = int(ref.get("number") or 0)
                except (TypeError, ValueError):
                    continue
                if ref_num <= 0:
                    continue
                ref_state = (ref.get("state") or "").upper()
                closing.append((ref_repo, ref_num, ref_state))
        except (KeyError, TypeError):
            pass
        out.setdefault(nwo, {})[num] = (head, review, ci_state, mergeable, title, body, base, closing)

    return out


def _graphql_pr_metadata(pr_numbers: dict[str, set[int]]) -> dict[str, dict[int, tuple]]:
    """Batch-fetch headRefName, reviewDecision, CI status, mergeable, title,
    body, baseRefName, and closing-issue references for known PR numbers.

    Splits the work into ``_PR_METADATA_CHUNK``-sized parallel requests.
    GitHub's GraphQL evaluates aliases mostly serially within one request, so
    many small concurrent requests finish in ~1/Nth of the wall-clock that a
    single large batch would take.

    Returns:
        {nwo: {number: (headRefName, reviewDecision, ciState, mergeable,
                          title, body, baseRefName,
                          closing_issues), ...}}

    `closing_issues` is a list of `(repo, num, state)` triples extracted from
    `closingIssuesReferences`. The list is `[]` when the PR closes no issues.
    """
    pairs: list[tuple[str, int]] = []
    for nwo, nums in pr_numbers.items():
        for n in nums:
            pairs.append((nwo, n))
    if not pairs:
        return {}

    chunks = [pairs[i : i + _PR_METADATA_CHUNK] for i in range(0, len(pairs), _PR_METADATA_CHUNK)]
    workers = max(1, min(IO_FANOUT_CAP, len(chunks)))
    out: dict[str, dict[int, tuple]] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        for chunk_out in pool.map(_graphql_pr_metadata_chunk, chunks):
            for nwo, num_map in chunk_out.items():
                out.setdefault(nwo, {}).update(num_map)
    return out


# Backport detection patterns. Patterns are intentionally tight to avoid false
# positives — generic PRs can have titles with brackets or mention `#NNN` in
# their body without being backports.
_BACKPORT_TITLE_RE = re.compile(r"^\[([^\]]+)\]\s+.*?\(#(\d+)\)\s*$")
_BACKPORT_TITLE_LOOSE_RE = re.compile(r"^\[([^\]]+)\]\s+")
_BACKPORT_BODY_RE = re.compile(r"\bBackports?(?:\s+of)?\s+#(\d+)", re.IGNORECASE)
_BACKPORT_BRANCH_RE = re.compile(r"^backport/([^/]+)/pr-(\d+)$")


def _detect_pr_backport(title: str, body: str, head_ref: str) -> tuple[str, int] | None:
    """Return (branch, parent_num) if this PR is a backport, else None.

    Detection priority:
      1. Title pattern `[<branch>] ... (#<parent>)` — the kibanamachine
         convention; the parent number is on the title itself and is the
         most authoritative source.
      2. Branch name `backport/<branch>/pr-<parent>` — mechanically created
         by backport tooling; the parent number is part of the branch name.
      3. Title `[<branch>] ...` + body `Backport of #<parent>` /
         `Backports #<parent>` — covers manual backports where the author
         left the body hint but didn't include `(#N)` in the title.
    """
    m = _BACKPORT_TITLE_RE.match(title or "")
    if m:
        try:
            return m.group(1), int(m.group(2))
        except (ValueError, IndexError):
            pass
    m = _BACKPORT_BRANCH_RE.match(head_ref or "")
    if m:
        try:
            return m.group(1), int(m.group(2))
        except (ValueError, IndexError):
            pass
    m_title = _BACKPORT_TITLE_LOOSE_RE.match(title or "")
    if m_title:
        m_body = _BACKPORT_BODY_RE.search(body or "")
        if m_body:
            try:
                return m_title.group(1), int(m_body.group(1))
            except (ValueError, IndexError):
                pass
    return None


_PHANTOM_PARENT_CAP = 30


def _graphql_phantom_parents(keys: list[tuple[str, int]]) -> dict[tuple[str, int], dict[str, str]]:
    """Fetch minimal metadata for backport parents not present in any section.

    Used when a backport child appears in a section (e.g. `Mine: Your open PRs`)
    but its merged parent does not — we still want to render the parent row so
    the family is visually anchored. One batched GraphQL call covers up to
    `_PHANTOM_PARENT_CAP` parents per refresh; anything beyond that falls back
    to a minimal phantom built from just the (repo, num) identity.
    """
    if not keys:
        return {}
    aliases: list[str] = []
    alias_map: dict[str, tuple[str, int]] = {}
    for nwo, n in keys[:_PHANTOM_PARENT_CAP]:
        owner, name = nwo.split("/", 1) if "/" in nwo else ("", nwo)
        alias = f"_ph{owner}_{name}_{n}".replace("-", "_")
        aliases.append(
            f'{alias}: repository(owner: "{owner}", name: "{name}") '
            f"{{ pullRequest(number: {n}) {{ number title state url "
            f"createdAt updatedAt author {{ login }} }} }}"
        )
        alias_map[alias] = (nwo, n)
    query = "query { " + " ".join(aliases) + " }"
    try:
        result = subprocess.run(
            ["gh", "api", "graphql", "-f", f"query={query}"],
            check=False,
            capture_output=True,
            text=True,
            timeout=20,
        )
        if not result.stdout.strip():
            return {}
        data = json.loads(result.stdout).get("data", {})
    except Exception:
        return {}
    out: dict[tuple[str, int], dict[str, str]] = {}
    for alias, key in alias_map.items():
        node = (data.get(alias) or {}).get("pullRequest")
        if not node:
            continue
        out[key] = {
            "title": node.get("title", "") or "",
            "state": (node.get("state", "") or "").lower(),
            "url": node.get("url", "") or "",
            "author": (node.get("author") or {}).get("login", "") or "",
            "created": node.get("createdAt", "") or "",
            "updated": node.get("updatedAt", "") or "",
        }
    return out


def _make_phantom_pr_parent(repo: str, num: int, data: dict[str, str] | None) -> dict[str, Any]:
    """Build a phantom-parent PR item dict from optional fetched metadata.

    `_phantom=True` lets the renderer (Phase polish) skip badges that depend on
    local-worktree presence or other per-PR state we haven't fetched. State is
    normalized to `merged`/`closed`/`open` so the icon picker behaves.
    """
    data = data or {}
    raw_state = (data.get("state") or "merged").lower()
    if raw_state in ("merged", "closed", "open"):
        state = raw_state
    else:
        state = "merged"
    return {
        "kind": "pr",
        "num": num,
        "repo": repo,
        "title": data.get("title") or f"#{num}",
        "url": data.get("url") or f"https://github.com/{repo}/pull/{num}",
        "state": state,
        "author": data.get("author", ""),
        "created": data.get("created", ""),
        "updated": data.get("updated", ""),
        "labels": [],
        "assignees": [],
        "comments": 0,
        "_tree_role": "parent",
        "_parent_id": "",
        "_phantom": True,
    }


def _group_pr_families(
    all_items: list[dict[str, Any]],
    pr_metadata: dict[str, dict[int, tuple]],
) -> None:
    """Detect PR backport families and reorder `all_items` in place.

    Per section:
      - For every PR with a detected parent (via title/body/branch), mark it
        as `_tree_role=child` and link to its parent via `_parent_id`.
      - If the parent is already in the same section, mark the parent as
        `_tree_role=parent` and reorder so children appear immediately after.
      - Otherwise, emit a phantom parent row immediately before the children.
        The phantom row carries `_phantom=True`.

    Sections that already have hierarchy (Maintenance, via
    `fetch_backport_failures`) are detected by the presence of `_tree_role`
    on their items and skipped. The Maintenance section's grouping is more
    authoritative because it walks bot comments + label states; we never
    second-guess it.
    """
    if not all_items:
        return

    sections: list[tuple[dict, list[dict]]] = []
    cur_header: dict | None = None
    cur_items: list[dict] = []
    for item in all_items:
        if item.get("_header"):
            if cur_header is not None:
                sections.append((cur_header, cur_items))
            cur_header = item
            cur_items = []
        else:
            cur_items.append(item)
    if cur_header is not None:
        sections.append((cur_header, cur_items))

    section_relations: list[tuple[dict, list[dict], dict[tuple[str, int], tuple[str, int, str]]]] = []
    phantom_needed: dict[tuple[str, int], None] = {}

    for header, items in sections:
        if any(it.get("_tree_role") for it in items):
            section_relations.append((header, items, {}))
            continue
        relations: dict[tuple[str, int], tuple[str, int, str]] = {}
        item_keys: set[tuple[str, int]] = set()
        for it in items:
            if it.get("num"):
                try:
                    item_keys.add((it["repo"], int(it["num"])))
                except (ValueError, TypeError):
                    pass
        for it in items:
            if it.get("kind") != "pr":
                continue
            repo = it.get("repo", "")
            try:
                num = int(it["num"])
            except (KeyError, ValueError, TypeError):
                continue
            meta = pr_metadata.get(repo, {}).get(num)
            if not meta or len(meta) < _PR_META_LEN:
                continue
            head = meta[0]
            title = it.get("title") or meta[_PR_META_TITLE] or ""
            body = meta[_PR_META_BODY] or ""
            detected = _detect_pr_backport(title, body, head)
            if not detected:
                continue
            branch, parent_num = detected
            if parent_num == num:
                continue
            relations[(repo, num)] = (repo, parent_num, branch)
            if (repo, parent_num) not in item_keys:
                phantom_needed[(repo, parent_num)] = None
        section_relations.append((header, items, relations))

    phantom_data: dict[tuple[str, int], dict[str, str]] = {}
    if phantom_needed:
        phantom_data = _graphql_phantom_parents(list(phantom_needed.keys()))

    new_items: list[dict[str, Any]] = []
    for header, items, relations in section_relations:
        new_items.append(header)
        if not relations:
            new_items.extend(items)
            continue

        item_by_key: dict[tuple[str, int], dict[str, Any]] = {}
        for it in items:
            try:
                item_by_key[(it["repo"], int(it["num"]))] = it
            except (KeyError, ValueError, TypeError):
                continue

        children_by_parent: dict[tuple[str, int], list[tuple[dict, str]]] = {}
        for (child_repo, child_num), (parent_repo, parent_num, branch) in relations.items():
            child = item_by_key.get((child_repo, child_num))
            if child is None:
                continue
            children_by_parent.setdefault((parent_repo, parent_num), []).append((child, branch))

        children_to_skip: set[tuple[str, int]] = set(relations.keys())
        emitted_parents: set[tuple[str, int]] = set()
        for it in items:
            try:
                key = (it["repo"], int(it["num"])) if it.get("num") is not None else None
            except (ValueError, TypeError):
                key = None
            if key in children_to_skip:
                continue
            if key in children_by_parent:
                it["_tree_role"] = "parent"
                it["_parent_id"] = ""
                new_items.append(it)
                emitted_parents.add(key)
                for child, branch in _sorted_children(children_by_parent[key]):
                    child["_tree_role"] = "child"
                    child["_parent_id"] = f"pr:{key[0]}:{key[1]}"
                    child["_tree_branch"] = branch
                    new_items.append(child)
            else:
                new_items.append(it)

        for (parent_repo, parent_num), kids in children_by_parent.items():
            if (parent_repo, parent_num) in emitted_parents:
                continue
            phantom = _make_phantom_pr_parent(parent_repo, parent_num, phantom_data.get((parent_repo, parent_num)))
            new_items.append(phantom)
            for child, branch in _sorted_children(kids):
                child["_tree_role"] = "child"
                child["_parent_id"] = f"pr:{parent_repo}:{parent_num}"
                child["_tree_branch"] = branch
                new_items.append(child)

    all_items[:] = new_items


def _sorted_children(pairs: list[tuple[dict, str]]) -> list[tuple[dict, str]]:
    """Return children sorted by tree_branch then PR number for stability."""
    return sorted(
        pairs,
        key=lambda pair: (
            str(pair[1] or "").lower(),
            int(pair[0].get("num") or 0),
        ),
    )


_ISSUE_METADATA_CHUNK = 10


def _graphql_issue_metadata_chunk(items: list[tuple[str, int]]) -> dict[str, dict[int, tuple]]:
    """Fetch parent + subIssuesSummary + closing-PR refs for a small batch.

    Per issue:
      - `parent { number title state repository { nameWithOwner } }` — direct
        epic / parent issue if any. Both number and repository may be cross-
        repo (parent in another repo of the same owner), so we capture both.
      - `subIssuesSummary { total completed }` — used to flag epics that have
        children even if none are in the current section (the parent then
        renders with an `N/M done` badge in the polish phase).
      - `closedByPullRequestsReferences(first: 5)` \u2014 PRs that would close this
        issue if merged. Powers PR \u2194 Issue cross-linking badges and same-
        section nesting.
    """
    aliases: list[str] = []
    alias_map: dict[str, tuple[str, int]] = {}
    for nwo, n in items:
        owner, name = nwo.split("/", 1) if "/" in nwo else ("", nwo)
        alias = f"_i{owner}_{name}_{n}".replace("-", "_")
        aliases.append(
            f'{alias}: repository(owner: "{owner}", name: "{name}") '
            f"{{ issue(number: {n}) {{ number "
            f"parent {{ number title state repository {{ nameWithOwner }} }} "
            f"subIssuesSummary {{ total completed }} "
            f"closedByPullRequestsReferences(first: {_CROSS_LINK_FETCH_LIMIT}) {{ nodes {{ "
            f"number state repository {{ nameWithOwner }} }} }} }} }}"
        )
        alias_map[alias] = (nwo, n)
    if not aliases:
        return {}
    query = "query { " + " ".join(aliases) + " }"
    try:
        result = subprocess.run(
            ["gh", "api", "graphql", "-f", f"query={query}"],
            check=False,
            capture_output=True,
            text=True,
            timeout=20,
        )
        if not result.stdout.strip():
            return {}
        data = json.loads(result.stdout).get("data", {})
    except Exception:
        return {}
    out: dict[str, dict[int, tuple]] = {}
    for alias, (nwo, num) in alias_map.items():
        node = (data.get(alias) or {}).get("issue")
        if not node:
            continue
        parent = node.get("parent") or {}
        try:
            parent_num = int(parent.get("number") or 0)
        except (TypeError, ValueError):
            parent_num = 0
        parent_title = parent.get("title", "") or ""
        parent_state = (parent.get("state", "") or "").lower()
        parent_repo = ((parent.get("repository") or {}).get("nameWithOwner")) or ""
        sub = node.get("subIssuesSummary") or {}
        try:
            sub_total = int(sub.get("total", 0) or 0)
            sub_completed = int(sub.get("completed", 0) or 0)
        except (TypeError, ValueError):
            sub_total = 0
            sub_completed = 0
        closed_by: list[tuple[str, int, str]] = []
        try:
            for ref in (node.get("closedByPullRequestsReferences") or {}).get("nodes") or []:
                if not ref:
                    continue
                ref_repo = ((ref.get("repository") or {}).get("nameWithOwner")) or nwo
                try:
                    ref_num = int(ref.get("number") or 0)
                except (TypeError, ValueError):
                    continue
                if ref_num <= 0:
                    continue
                ref_state = (ref.get("state") or "").upper()
                closed_by.append((ref_repo, ref_num, ref_state))
        except (KeyError, TypeError):
            pass
        out.setdefault(nwo, {})[num] = (
            parent_repo,
            parent_num,
            parent_title,
            parent_state,
            sub_total,
            sub_completed,
            closed_by,
        )
    return out


def _graphql_issue_metadata(issue_numbers: dict[str, set[int]]) -> dict[str, dict[int, tuple]]:
    """Batch-fetch parent + subIssuesSummary + closing-PR refs for issues.

    Splits work into ``_ISSUE_METADATA_CHUNK``-sized parallel requests. The
    batch size is larger than the PR fetch because each issue alias is
    cheaper (no commits/checks subtree); 10 keeps wall-clock low while
    staying well within the GraphQL alias limit.

    Returns:
        {nwo: {number: (parent_repo, parent_num, parent_title, parent_state,
                          sub_total, sub_completed, closed_by), ...}}

    `closed_by` is a list of `(repo, num, state)` triples extracted from
    `closedByPullRequestsReferences`. The list is `[]` when no PR closes this
    issue.
    """
    pairs: list[tuple[str, int]] = []
    for nwo, nums in issue_numbers.items():
        for n in nums:
            pairs.append((nwo, n))
    if not pairs:
        return {}

    chunks = [pairs[i : i + _ISSUE_METADATA_CHUNK] for i in range(0, len(pairs), _ISSUE_METADATA_CHUNK)]
    workers = max(1, min(IO_FANOUT_CAP, len(chunks)))
    out: dict[str, dict[int, tuple]] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        for chunk_out in pool.map(_graphql_issue_metadata_chunk, chunks):
            for nwo, num_map in chunk_out.items():
                out.setdefault(nwo, {}).update(num_map)
    return out


def _make_phantom_issue_parent(repo: str, num: int, title: str, state: str) -> dict[str, Any]:
    """Build a phantom epic-parent issue item dict.

    Used when a child issue's epic is in a different section or repo and
    we want the picker to anchor the family visually. `_phantom=True` lets
    the renderer skip metadata-derived columns the phantom doesn't have.
    """
    s = (state or "").lower()
    if s not in ("open", "closed", "not_planned"):
        s = "open"
    return {
        "kind": "issue",
        "num": num,
        "repo": repo,
        "title": title or f"#{num}",
        "url": f"https://github.com/{repo}/issues/{num}",
        "state": s,
        "author": "",
        "assignee": "",
        "labels": [],
        "assignees": [],
        "comments": 0,
        "created": "",
        "updated": "",
        "_tree_role": "parent",
        "_parent_id": "",
        "_phantom": True,
    }


def _group_issue_families(
    all_items: list[dict[str, Any]],
    issue_metadata: dict[str, dict[int, tuple]],
) -> None:
    """Group issues under epic parents per section.

    Per section:
      - For every issue with a `parent` field, mark as `_tree_role=child`
        and link to the parent via `_parent_id=issue:repo:num`.
      - If the parent issue is in the same section, mark it as
        `_tree_role=parent`.
      - Otherwise, emit a phantom parent row before the children.
      - For every issue with `subIssuesSummary.total > 0` that isn't already
        a child, mark it as `_tree_role=parent` and stash sub counts under
        `_sub_total` / `_sub_completed` for the renderer.

    Sections that already have hierarchy (PR families from
    `_group_pr_families`, or the Maintenance section) are left alone. We
    never second-guess a more authoritative grouping pass that already ran.
    """
    if not all_items:
        return

    sections: list[tuple[dict, list[dict]]] = []
    cur_header: dict | None = None
    cur_items: list[dict] = []
    for item in all_items:
        if item.get("_header"):
            if cur_header is not None:
                sections.append((cur_header, cur_items))
            cur_header = item
            cur_items = []
        else:
            cur_items.append(item)
    if cur_header is not None:
        sections.append((cur_header, cur_items))

    section_relations: list[
        tuple[
            dict,
            list[dict],
            dict[tuple[str, int], tuple[str, int, str, str]],
            set[tuple[str, int]],
        ]
    ] = []

    for header, items in sections:
        if any(it.get("_tree_role") for it in items):
            section_relations.append((header, items, {}, set()))
            continue
        relations: dict[tuple[str, int], tuple[str, int, str, str]] = {}
        epic_parents: set[tuple[str, int]] = set()
        for it in items:
            if it.get("kind") != "issue":
                continue
            repo = it.get("repo", "")
            try:
                num = int(it["num"])
            except (KeyError, ValueError, TypeError):
                continue
            meta = issue_metadata.get(repo, {}).get(num)
            if not meta:
                continue
            (
                parent_repo,
                parent_num,
                parent_title,
                parent_state,
                sub_total,
                sub_completed,
                *_,
            ) = meta
            if parent_num and parent_repo:
                relations[(repo, num)] = (parent_repo, parent_num, parent_title, parent_state)
            if sub_total > 0:
                epic_parents.add((repo, num))
                it["_sub_total"] = sub_total
                it["_sub_completed"] = sub_completed
        section_relations.append((header, items, relations, epic_parents))

    new_items: list[dict[str, Any]] = []
    for header, items, relations, epic_parents in section_relations:
        new_items.append(header)
        if not relations and not epic_parents:
            new_items.extend(items)
            continue

        item_by_key: dict[tuple[str, int], dict[str, Any]] = {}
        for it in items:
            try:
                item_by_key[(it["repo"], int(it["num"]))] = it
            except (KeyError, ValueError, TypeError):
                continue

        children_by_parent: dict[tuple[str, int], list[tuple[dict, str, str]]] = {}
        for (child_repo, child_num), (parent_repo, parent_num, parent_title, parent_state) in relations.items():
            child = item_by_key.get((child_repo, child_num))
            if child is None:
                continue
            children_by_parent.setdefault((parent_repo, parent_num), []).append((child, parent_title, parent_state))

        children_to_skip: set[tuple[str, int]] = set(relations.keys())
        emitted_parents: set[tuple[str, int]] = set()
        for it in items:
            try:
                key = (it["repo"], int(it["num"])) if it.get("num") is not None else None
            except (ValueError, TypeError):
                key = None
            if key in children_to_skip:
                continue
            if key in children_by_parent or key in epic_parents:
                it["_tree_role"] = "parent"
                it["_parent_id"] = ""
                new_items.append(it)
                emitted_parents.add(key)
                if key in children_by_parent:
                    for child, _ptitle, _pstate in sorted(
                        children_by_parent[key], key=lambda c: int(c[0].get("num") or 0)
                    ):
                        child["_tree_role"] = "child"
                        child["_parent_id"] = f"issue:{key[0]}:{key[1]}"
                        new_items.append(child)
            else:
                new_items.append(it)

        for (parent_repo, parent_num), kids in children_by_parent.items():
            if (parent_repo, parent_num) in emitted_parents:
                continue
            _first_child, parent_title, parent_state = kids[0]
            phantom = _make_phantom_issue_parent(parent_repo, parent_num, parent_title, parent_state)
            new_items.append(phantom)
            for child, _ptitle, _pstate in sorted(kids, key=lambda c: int(c[0].get("num") or 0)):
                child["_tree_role"] = "child"
                child["_parent_id"] = f"issue:{parent_repo}:{parent_num}"
                new_items.append(child)

    all_items[:] = new_items


def _attach_cross_links(
    all_items: list[dict[str, Any]],
    gql_data: dict[str, dict[int, tuple]],
    issue_meta: dict[str, dict[int, tuple]],
) -> None:
    """Attach the best PR \u2194 Issue cross-link partner to every item.

    Stores `_cross_link` on each item as `(partner_kind, partner_repo,
    partner_num, partner_state)` or leaves the field absent when no relevant
    link exists.

    Selection rule: prefer an OPEN partner. Fall back to the first reference
    in the GraphQL list. We only ever render one badge per row.
    """

    def _pick(refs: list[tuple[str, int, str]]) -> tuple[str, int, str] | None:
        if not refs:
            return None
        for repo, num, state in refs:
            if (state or "").upper() == "OPEN":
                return (repo, num, "OPEN")
        return refs[0]

    for item in all_items:
        kind = item.get("kind")
        repo = item.get("repo") or ""
        try:
            num = int(item.get("num") or 0)
        except (TypeError, ValueError):
            continue
        if not repo or num <= 0:
            continue

        if kind == "pr":
            meta = gql_data.get(repo, {}).get(num)
            if not meta or len(meta) <= _PR_META_CLOSES:
                continue
            picked = _pick(meta[_PR_META_CLOSES] or [])
            if picked is None:
                continue
            item["_cross_link"] = ("issue", picked[0], picked[1], picked[2])

        elif kind == "issue":
            meta = issue_meta.get(repo, {}).get(num)
            if not meta or len(meta) < 7:
                continue
            picked = _pick(meta[6] or [])
            if picked is None:
                continue
            item["_cross_link"] = ("pr", picked[0], picked[1], picked[2])


def _group_cross_link_pairs(all_items: list[dict[str, Any]]) -> None:
    """Same-section bonus nesting: if a section contains a loose issue and
    a loose PR that closes it, nest the PR under the issue.

    Skipped when either side already participates in a family (epic /
    backport) \u2014 the 2-level depth limit is preserved, and badges remain the
    universal cross-link signal. Both items must live in the same section
    because the picker treats sections as intent boundaries.
    """
    if not all_items:
        return

    sections: list[tuple[int, int]] = []
    current_start = -1
    for idx, it in enumerate(all_items):
        if it.get("_header"):
            if current_start >= 0:
                sections.append((current_start, idx))
            current_start = idx + 1
    if current_start >= 0:
        sections.append((current_start, len(all_items)))

    new_items: list[dict[str, Any]] | None = None

    for start, end in sections:
        section_slice = all_items[start:end]
        loose_index: dict[tuple[str, str, int], int] = {}
        for offset, it in enumerate(section_slice):
            if it.get("_tree_role"):
                continue
            kind = it.get("kind") or ""
            try:
                num = int(it.get("num") or 0)
            except (TypeError, ValueError):
                continue
            repo = it.get("repo") or ""
            if not repo or not kind or num <= 0:
                continue
            loose_index[(kind, repo, num)] = offset

        pairings: list[tuple[int, int]] = []
        seen_prs: set[int] = set()
        for (kind, repo, num), offset in loose_index.items():
            if kind != "issue":
                continue
            issue_item = section_slice[offset]
            link = issue_item.get("_cross_link")
            if not link or link[0] != "pr":
                continue
            _, pr_repo, pr_num, _state = link
            pr_offset = loose_index.get(("pr", pr_repo, int(pr_num)))
            if pr_offset is None:
                continue
            if pr_offset in seen_prs:
                continue
            seen_prs.add(pr_offset)
            pairings.append((offset, pr_offset))

        if not pairings:
            continue

        if new_items is None:
            new_items = list(all_items)

        pr_to_issue: dict[int, int] = {pr_off: iss_off for iss_off, pr_off in pairings}

        reordered: list[dict[str, Any]] = []
        emitted = set()
        for offset, it in enumerate(section_slice):
            if offset in pr_to_issue:
                continue
            if offset in {iss_off for iss_off, _ in pairings}:
                it["_tree_role"] = "parent"
                it["_parent_id"] = ""
                reordered.append(it)
                emitted.add(offset)
                pr_offset = next(p for i, p in pairings if i == offset)
                pr_item = section_slice[pr_offset]
                pr_item["_tree_role"] = "child"
                pr_item["_parent_id"] = f"issue:{it.get('repo')}:{int(it.get('num') or 0)}"
                pr_item.setdefault("_tree_branch", "")
                reordered.append(pr_item)
                emitted.add(pr_offset)
            elif offset not in emitted:
                reordered.append(it)

        new_items[start:end] = reordered

    if new_items is not None:
        all_items[:] = new_items


def _section_scopes(section: dict[str, Any]) -> list[str]:
    raw = section.get("scopes", section.get("scope", []))
    if isinstance(raw, str):
        values = [part.strip() for part in raw.split(",")]
    elif isinstance(raw, list):
        values = [str(part).strip() for part in raw]
    else:
        values = []
    return [value for value in values if value]


def parse_config(config_path: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, str]]:
    """Parse gh-dash YAML config using yq. Returns (pr_sections, issue_sections, repo_paths)."""
    pr_sections: list[dict[str, Any]] = []
    issue_sections: list[dict[str, Any]] = []
    repo_paths: dict[str, str] = {}

    # Restore-time contention (many tmux hooks firing at once after a server
    # restore) can make a single `yq` invocation exceed a tight timeout even
    # though the config itself is tiny and valid. Use a more forgiving timeout
    # and one retry so a transient stall does not surface as a parse failure.
    last_exc: Exception | None = None
    data: Any = None
    for attempt in range(2):
        try:
            raw = subprocess.run(
                ["yq", "-o", "json", ".", config_path],
                check=True,
                capture_output=True,
                text=True,
                timeout=15,
            ).stdout
            data = json.loads(raw)
            last_exc = None
            break
        except Exception as e:
            last_exc = e
            if attempt == 0:
                time.sleep(0.25)
    if last_exc is not None:
        print(f"Failed to parse config: {last_exc}", file=sys.stderr)
        return [], [], {}

    for s in data.get("prSections") or []:
        title = s.get("title", "")
        filters = s.get("filters", "")
        if title and filters:
            entry: dict[str, Any] = {"title": title, "filters": filters.strip()}
            if s.get("source"):
                entry["source"] = s["source"]
            scopes = _section_scopes(s)
            if scopes:
                entry["scopes"] = scopes
            pr_sections.append(entry)

    for s in data.get("issuesSections") or []:
        title = s.get("title", "")
        filters = s.get("filters", "")
        if title and filters:
            entry = {"title": title, "filters": filters.strip()}
            scopes = _section_scopes(s)
            if scopes:
                entry["scopes"] = scopes
            issue_sections.append(entry)

    for k, v in (data.get("repoPaths") or {}).items():
        repo_paths[str(k)] = str(v)

    return pr_sections, issue_sections, repo_paths


def _section_scope_map(
    pr_sections: list[dict[str, Any]],
    issue_sections: list[dict[str, Any]],
) -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    for i, section in enumerate(pr_sections):
        scopes = {str(v) for v in section.get("scopes", []) if str(v)}
        out[f"pr:{i}"] = scopes
    for i, section in enumerate(issue_sections):
        scopes = {str(v) for v in section.get("scopes", []) if str(v)}
        out[f"issue:{i}"] = scopes
    return out


def _scope_matches(section_id: str, scope: str, scope_map: dict[str, set[str]]) -> bool:
    if not scope or scope == "all":
        return True
    scopes = scope_map.get(section_id) or set()
    return scope in scopes


def _filter_lines_for_scope(lines: list[str], scope: str, scope_map: dict[str, set[str]]) -> list[str]:
    if not scope or scope == "all":
        return list(lines)

    out: list[str] = []
    include_current = False
    for line in lines:
        parts = line.split("\t")
        if len(parts) >= 4 and parts[1] == "header":
            section_id = parts[3].strip()
            include_current = _scope_matches(section_id, scope, scope_map)
        if include_current:
            out.append(line)
    return out


# TSV column indices (0-based). Kept in sync with `format_lines`. Header rows
# leave the per-item columns empty; family rows fill `parent_id`, `tree_role`,
# and `tree_branch` so the picker, sorter, and offsets writer can reason about
# parent/child blocks without re-parsing the display string.
_COL_DISPLAY = 0
_COL_KIND = 1
_COL_REPO = 2
_COL_NUM = 3
_COL_URL = 4
_COL_SEARCH = 5
_COL_META = 6
_COL_MERGEABLE = 7
_COL_SECTION = 8
_COL_SORT_CREATED = 9
_COL_SORT_UPDATED = 10
_COL_PARENT_ID = 11
_COL_TREE_ROLE = 12
_COL_TREE_BRANCH = 13
_TSV_COLS = 14

# Regex matching real section-header section_ids (`pr:0`, `issue:3`). Backport
# placeholder rows use `kind=header` with `num=0` and must not be treated as
# section anchors by the jump/offsets pipeline.
_SECTION_ID_RE = re.compile(r"^(pr|issue):\d+$")


SORT_KEYS = ("created-desc", "updated-desc", "age-asc", "repo-asc")


def _parent_identity_of(parts: list[str]) -> str:
    """Return the `kind:repo:num` identity for a row, or empty if incomplete.

    Used by sort + collapse + mark-subtree paths to match children back to
    their parent. Real section headers (empty repo) never produce an identity.
    """
    kind = parts[_COL_KIND] if len(parts) > _COL_KIND else ""
    repo = parts[_COL_REPO] if len(parts) > _COL_REPO else ""
    num = parts[_COL_NUM] if len(parts) > _COL_NUM else ""
    if not kind or not repo or not num or kind == "header":
        return ""
    return f"{kind}:{repo}:{num}"


def _tree_role_of(parts: list[str]) -> str:
    return parts[_COL_TREE_ROLE] if len(parts) > _COL_TREE_ROLE else ""


def _parent_id_of(parts: list[str]) -> str:
    return parts[_COL_PARENT_ID] if len(parts) > _COL_PARENT_ID else ""


def _sort_within_sections(lines: list[str], sort_key: str) -> list[str]:
    """Re-sort family blocks within each section by `sort_key`.

    A family block is one of:
      - a parent row + every immediately-following child row whose
        `parent_id` points back at the parent's `kind:repo:num` identity, OR
      - a single loose row.

    Blocks are sorted using the parent (or loose) row's key. Children inside
    a block are re-sorted by the same key so the visible hierarchy stays
    consistent across all four sort modes. Section headers and section-level
    backport placeholders (`kind=header` with no `kind:repo:num` identity)
    stay anchored in their original positions; the sort runs section-by-
    section between them.
    """
    if not sort_key or sort_key == "created-desc":
        return list(lines)
    if sort_key not in SORT_KEYS:
        return list(lines)

    def key_for(parts: list[str]) -> tuple:
        if sort_key == "updated-desc":
            updated = parts[_COL_SORT_UPDATED] if len(parts) > _COL_SORT_UPDATED else ""
            return (_desc_key(updated),)
        if sort_key == "age-asc":
            created = parts[_COL_SORT_CREATED] if len(parts) > _COL_SORT_CREATED else ""
            return (created,)
        if sort_key == "repo-asc":
            repo = parts[_COL_REPO].lower() if len(parts) > _COL_REPO else ""
            created = parts[_COL_SORT_CREATED] if len(parts) > _COL_SORT_CREATED else ""
            return (repo, created)
        return ("",)

    out: list[str] = []
    blocks: list[tuple[tuple, list[str]]] = []

    def flush() -> None:
        if not blocks:
            return
        out.extend(line for _, block in sorted(blocks, key=lambda entry: entry[0]) for line in block)
        blocks.clear()

    pending: list[str] | None = None
    pending_key: tuple | None = None
    pending_identity = ""

    def close_pending() -> None:
        nonlocal pending, pending_key, pending_identity
        if pending is not None and pending_key is not None:
            # Re-sort children inside the block by the same key. The parent
            # row stays in slot 0; everything after it is children.
            if len(pending) > 1:
                head = pending[0]
                tail = pending[1:]
                tail_sorted = sorted(tail, key=lambda ln: key_for(ln.split("\t")))
                pending = [head] + tail_sorted
            blocks.append((pending_key, pending))
        pending = None
        pending_key = None
        pending_identity = ""

    for line in lines:
        parts = line.split("\t")
        kind = parts[_COL_KIND] if len(parts) > _COL_KIND else ""
        role = _tree_role_of(parts)

        if kind == "header" and _parent_identity_of(parts) == "":
            # Real section header. Close everything before it.
            close_pending()
            flush()
            out.append(line)
            continue

        if role == "parent":
            close_pending()
            pending = [line]
            pending_key = key_for(parts)
            pending_identity = _parent_identity_of(parts)
            continue

        if role == "child" and pending is not None and _parent_id_of(parts) == pending_identity:
            pending.append(line)
            continue

        # Loose row, orphan child, or anything else: own block.
        close_pending()
        blocks.append((key_for(parts), [line]))

    close_pending()
    flush()
    return out


def _desc_key(value: str) -> str:
    """Return an inverted sort key so ascending order yields newest-first.

    Used by `updated-desc` so a single `sorted(..., key=...)` call covers
    every block; mixing `reverse=True` with stable per-key block ordering is
    awkward when children inside a block also need the same direction.
    """
    if not value:
        return "\uffff"
    return "".join(chr(0x10FFFE - (ord(ch) & 0xFFFF)) for ch in value)


def _write_offsets(
    cache_dir: str,
    mode: str,
    scope: str,
    lines: list[str],
) -> None:
    """Persist a 1-indexed row index per real section header.

    Consumed by `alt-n` / `alt-p` (jump) and `alt-S` (sort cycler). Only true
    section headers — `kind=header` whose `num` column (col 4) matches
    `(pr|issue):\\d+` — are emitted. Family parents are `kind=pr`/`issue` and
    are excluded by design, as are backport placeholder rows that re-use
    `kind=header` for visual layout. The file is overwritten on every scope
    or sort change.
    """
    try:
        cache_dir_path = Path(cache_dir)
        cache_dir_path.mkdir(parents=True, exist_ok=True)
    except Exception:
        return

    headers: list[dict[str, Any]] = []
    for idx, line in enumerate(lines, start=1):
        parts = line.split("\t")
        if len(parts) >= 4 and parts[1] == "header":
            section_id = parts[3].strip()
            if not _SECTION_ID_RE.match(section_id):
                continue
            title = parts[5].strip() if len(parts) > 5 else ""
            headers.append({"row": idx, "section_id": section_id, "title": title})

    payload = {
        "version": 1,
        "mode": mode,
        "scope": scope,
        "total_rows": len(lines),
        "headers": headers,
    }
    out_path = cache_dir_path / f"gh_picker_offsets_{mode}_{scope}.json"
    try:
        _atomic_write_text(str(out_path), json.dumps(payload))
    except Exception:
        pass


def _read_collapsed_set(cache_dir: str, mode: str) -> set[str]:
    """Read the collapsed-parents state file for the given mode.

    Returns an empty set on any read/parse error. Keys are
    `kind:repo:num` parent identities, one per line. Surrounding whitespace
    is stripped. Empty lines and lines starting with `#` are ignored so the
    file can grow comments without breaking parsing.
    """
    try:
        raw = (Path(cache_dir) / f"gh_picker_collapsed_{mode}").read_text(encoding="utf-8")
    except Exception:
        return set()
    out: set[str] = set()
    for line in raw.splitlines():
        token = line.strip()
        if not token or token.startswith("#"):
            continue
        out.add(token)
    return out


def _apply_collapsed_state(lines: list[str], collapsed: set[str]) -> list[str]:
    """Hide children of collapsed parents and decorate parent display.

    For every line whose `parent_id` (col 11) is in `collapsed`, the row is
    dropped. For every line whose `kind:repo:num` matches a key in
    `collapsed`, the display is suffixed with ` ▸ (N hidden)`. Expanded
    parents get a `▾` glyph for symmetry. Glyphs are dim cyan and placed
    after the existing display so they don't shift the column alignment of
    the body content.

    Returns a new list; the input is left untouched.
    """
    if not lines:
        return list(lines)
    hidden_counts: dict[str, int] = {}
    if collapsed:
        for line in lines:
            parts = line.split("\t")
            parent_ref = _parent_id_of(parts)
            if parent_ref and parent_ref in collapsed:
                hidden_counts[parent_ref] = hidden_counts.get(parent_ref, 0) + 1

    out: list[str] = []
    for line in lines:
        parts = line.split("\t")
        role = _tree_role_of(parts)
        parent_ref = _parent_id_of(parts)
        identity = _parent_identity_of(parts)

        if role == "child" and parent_ref in collapsed:
            continue

        if role == "parent" and identity:
            if identity in collapsed:
                hidden = hidden_counts.get(identity, 0)
                suffix = c("2;38;5;81", "  ▸") + (c("2;38;5;244", f" ({hidden} hidden)") if hidden else "")
                parts[_COL_DISPLAY] = parts[_COL_DISPLAY] + suffix
                line = "\t".join(parts)
            else:
                # Only annotate expanded parents that actually have visible
                # children — otherwise the glyph is misleading. Visible
                # children are any row beneath the parent with matching
                # parent_id that we will keep.
                pass

        out.append(line)
    return out


def _read_sort_key(cache_dir: str) -> str:
    try:
        raw = (Path(cache_dir) / "gh_picker_sort").read_text(encoding="utf-8").strip()
    except Exception:
        return "created-desc"
    if raw in SORT_KEYS:
        return raw
    return "created-desc"


def _annotate_section_counts(items: list[dict[str, Any]]) -> None:
    """Stamp count + age range + family/epic/done counts on each section header.

    `_count` is the total number of items (parents + children + loose), so
    the user-visible item total matches what they would see if they hand-
    counted rows. `_epic_count` tracks epics (issues with sub-issues),
    `_family_count` tracks PR backport families, and `_done_count` is the
    sum of `subIssuesSummary.completed` for every epic in the section. The
    header renderer composes these into the dim divider line.
    """
    header: dict[str, Any] | None = None
    count = 0
    epics = 0
    families = 0
    done = 0
    ages: list[str] = []

    def flush_header() -> None:
        if header is None:
            return
        header["_count"] = count
        if epics:
            header["_epic_count"] = epics
        if families:
            header["_family_count"] = families
        if done:
            header["_done_count"] = done
        if ages:
            ordered = sorted(ages)
            header["_newest"] = relative_date(ordered[-1])
            header["_oldest"] = relative_date(ordered[0])

    for item in items:
        if item.get("_header"):
            flush_header()
            header = item
            count = 0
            epics = 0
            families = 0
            done = 0
            ages = []
            continue
        if header is not None:
            count += 1
            if item.get("_tree_role") == "parent":
                kind = str(item.get("kind") or "")
                if kind == "issue" and int(item.get("_sub_total") or 0) > 0:
                    epics += 1
                    done += int(item.get("_sub_completed") or 0)
                elif kind == "pr":
                    families += 1
            age = str(item.get("created") or item.get("updated") or "")
            if age:
                ages.append(age)
    if header is not None:
        flush_header()


def _section_reason(filters: str, source: str = "") -> str:
    # Only treat tokens as positive when they are not negated. GitHub Search
    # uses `-token` to negate; we mirror that by walking whitespace-split tokens
    # and keeping the leading `-` out of any positive token set.
    positive: set[str] = set()
    for token in filters.split():
        if token.startswith("-"):
            continue
        positive.add(token.lower())
    reasons: list[str] = []
    if source == "backport-failures":
        reasons.append("pending backports")
    if "review-requested:@me" in positive:
        reasons.append("needs my review")
    if any(tok.startswith("team-review-requested:") for tok in positive):
        reasons.append("team review queue")
    if "author:@me" in positive:
        reasons.append("created by me")
    if "assignee:@me" in positive:
        reasons.append("assigned to me")
    if "mentions:@me" in positive:
        reasons.append("mentions me")
    if "involves:@me" in positive:
        reasons.append("involves me")
    if 'label:"failed-test"' in positive or "label:failed-test" in positive:
        reasons.append("failed-test radar")
    if not reasons:
        reasons.append("configured search")
    return ", ".join(reasons[:2])


def _search_blob(*values: Any) -> str:
    parts: list[str] = []
    for value in values:
        if value is None:
            continue
        if isinstance(value, (list, tuple, set)):
            parts.extend(str(v) for v in value if v)
        else:
            text = str(value)
            if text:
                parts.append(text)
    return " ".join(parts)


ICON_LOCAL = c("38;5;81", "◆")
ICON_LOCAL_SPACER = " "
REVIEW_APPROVED = c("38;5;42", "\U000f012c")
REVIEW_CHANGES = c("38;5;196", "\U000f0028")
REVIEW_PENDING = c("38;5;220", "\uf444")
REVIEW_SPACER = " "
REVIEW_APPROVED_STALE = c("2;38;5;42", "\U000f012c")
REVIEW_CHANGES_STALE = c("2;38;5;196", "\U000f0028")
REVIEW_PENDING_STALE = c("2;38;5;220", "\uf444")
CI_SUCCESS = c("38;5;42", "\uf4a4")
CI_FAILURE = c("38;5;196", "\uf530")
CI_PENDING = c("38;5;220", "\uf43a")
CI_SPACER = " "
CI_SUCCESS_STALE = c("2;38;5;42", "\uf4a4")
CI_FAILURE_STALE = c("2;38;5;196", "\uf530")
CI_PENDING_STALE = c("2;38;5;220", "\uf43a")
COMMENT_ICON = "\033[38;5;244m\U0001f4ac\033[0m"
CONFLICT_BADGE = c("38;5;209", "⚡")
CONFLICT_BADGE_STALE = c("2;38;5;209", "⚡")
CONFLICT_SPACER = " "


def _read_prior_pr_badges(cache_file: str) -> dict[tuple[str, int], tuple[str, str, str]]:
    """Best-effort: preserve PR badges across partial refreshes.

    If GitHub GraphQL metadata fetch fails, mergeable/review/ci state can go
    missing and badges would disappear. Since the picker is stale-while-revalidate,
    keep last-known badges in a clearly-stale (dim) style until fresh metadata
    is available.
    """
    try:
        raw = Path(cache_file).read_text(encoding="utf-8", errors="replace")
    except Exception:
        return {}

    out: dict[tuple[str, int], tuple[str, str, str]] = {}
    for line in raw.splitlines():
        if "\t" not in line:
            continue
        parts = line.rstrip("\n").split("\t")
        if len(parts) < 4:
            continue
        display, kind, repo, num_s = parts[0], parts[1], parts[2], parts[3]
        if kind != "pr":
            continue
        review = ""
        ci = ""
        if len(parts) >= 7 and parts[6]:
            meta_parts = parts[6].split(",", 1)
            review = meta_parts[0] if meta_parts else ""
            ci = meta_parts[1] if len(meta_parts) > 1 else ""
        mergeable = ""
        if len(parts) >= 8 and parts[7]:
            mergeable = parts[7]
        else:
            # Backward-compatible fallback: infer conflict from display.
            pos = display.find("⚡")
            if 0 <= pos:
                mergeable = "CONFLICTING"
        try:
            out[(repo, int(num_s))] = (review, ci, mergeable)
        except ValueError:
            continue
    return out


def _read_prior_sections(cache_file: str) -> dict[str, list[str]]:
    """Read previous TSV and group lines by section id (e.g. 'pr:0', 'issue:3')."""
    try:
        raw = Path(cache_file).read_text(encoding="utf-8", errors="replace")
    except Exception:
        return {}
    out: dict[str, list[str]] = {}
    cur_id = ""
    cur_lines: list[str] = []
    for line in raw.splitlines():
        if "\t" not in line:
            continue
        parts = line.split("\t")
        if len(parts) < 4:
            continue
        kind = parts[1]
        if kind == "header":
            if cur_id and cur_lines:
                out[cur_id] = cur_lines
            cur_id = parts[3].strip()
            cur_lines = [line]
        else:
            if cur_id:
                cur_lines.append(line)
    if cur_id and cur_lines:
        out[cur_id] = cur_lines
    return out


def _current_login() -> str:
    try:
        proc = subprocess.run(
            ["gh", "api", "user", "--jq", ".login"],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return proc.stdout.strip() if proc.returncode == 0 else ""
    except Exception:
        return ""


def _search_filter_tokens(filters: str) -> list[str]:
    try:
        return shlex.split(filters)
    except ValueError:
        return filters.split()


def _resolve_user_filter_value(value: str, viewer_login: str) -> str:
    value = value.strip()
    if value.lower() == "@me":
        return viewer_login.lower()
    if value.startswith("@"):
        value = value[1:]
    return value.lower()


def _matches_user_filter(current_values: list[str], filter_value: str, viewer_login: str) -> bool | None:
    expected = _resolve_user_filter_value(filter_value, viewer_login)
    if not expected:
        return None
    return expected in {v.lower() for v in current_values if v}


def _matches_is_filter(kind: str, item: dict[str, Any], value: str) -> bool | None:
    value = value.lower()
    state = (item.get("s") or "open").lower()
    merged = kind == "pr" and bool(item.get("m"))
    if value == "pr":
        return kind == "pr"
    if value == "issue":
        return kind == "issue"
    if value == "open":
        return state == "open" and not merged
    if value == "closed":
        return state == "closed"
    if value == "merged":
        return merged
    if value == "draft":
        return kind == "pr" and bool(item.get("d"))
    return None


def _matches_current_search_filters(
    item: dict[str, Any],
    kind: str,
    filters: str,
    viewer_login: str,
) -> bool:
    """Drop stale GitHub search hits when the returned item no longer matches.

    GitHub's search index can lag issue metadata changes. The search response
    still carries current-ish item fields, so re-check the qualifiers we can
    prove locally from that payload before writing a refreshed picker cache.
    """
    repo = str(item.get("r") or "")
    owner = repo.split("/", 1)[0].lower() if "/" in repo else ""
    author = str(item.get("a") or "")
    assignees = [str(v) for v in (item.get("assignees") or []) if v]
    labels = {str(v).lower() for v in (item.get("labels") or []) if v}

    for token in _search_filter_tokens(filters):
        negated = token.startswith("-")
        if negated:
            token = token[1:]
        if ":" not in token:
            continue

        key, value = token.split(":", 1)
        key = key.lower()
        value = value.strip()
        matched: bool | None = None

        if key == "is":
            matched = _matches_is_filter(kind, item, value)
        elif key == "author":
            matched = _matches_user_filter([author], value, viewer_login)
        elif key == "assignee":
            matched = _matches_user_filter(assignees, value, viewer_login)
        elif key == "label":
            matched = value.lower() in labels
        elif key == "org":
            matched = owner == value.lower()
        elif key == "repo":
            matched = repo.lower() == value.lower()

        if matched is None:
            continue
        if negated:
            matched = not matched
        if not matched:
            return False

    return True


def fetch_section(
    kind: str,
    idx: int,
    title: str,
    filters: str,
    limit: int = 30,
    viewer_login: str = "",
) -> list[dict[str, Any]]:
    """Fetch a single section from GitHub Search API. Returns item dicts."""
    header: dict[str, Any] = {"_header": True, "kind": kind, "idx": idx, "title": title, "_fetch_error": False}
    jq_expr = (
        "[.items[] | {"
        "n: .number, "
        "t: .title, "
        'r: (.repository_url | split("/") | .[-2:] | join("/")), '
        'u: (.updated_at | split("T")[0]), '
        "cr: .created_at, "
        "url: .html_url, "
        "d: .draft, "
        "a: .user.login, "
        'as: (.assignees[0].login // ""), '
        "assignees: [.assignees[].login], "
        "labels: [.labels[].name], "
        "c: .comments, "
        "s: .state, "
        "sr: .state_reason, "
        "m: .pull_request.merged_at"
        "}]"
    )

    try:
        proc = subprocess.run(
            [
                "gh",
                "api",
                "search/issues",
                "--method",
                "GET",
                "-f",
                f"q={filters}",
                "-f",
                f"per_page={limit}",
                "-f",
                "sort=created",
                "-f",
                "order=desc",
                "--jq",
                jq_expr,
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if proc.returncode != 0 or not proc.stdout.strip():
            header["_fetch_error"] = True
            return [header]
        items = json.loads(proc.stdout)
    except Exception:
        header["_fetch_error"] = True
        return [header]

    if not items:
        return [header]

    result: list[dict[str, Any]] = [header]
    section_items: list[dict[str, Any]] = []
    for item in items:
        if not item.get("n"):
            continue
        if not _matches_current_search_filters(item, kind, filters, viewer_login):
            continue
        is_pr = kind == "pr"
        state = (item.get("s") or "open").lower()
        merged = is_pr and bool(item.get("m"))
        if merged:
            effective_state = "merged"
        elif state == "closed" and not is_pr:
            sr = (item.get("sr") or "").lower()
            effective_state = "not_planned" if sr == "not_planned" else "closed"
        elif state == "closed":
            effective_state = "closed"
        else:
            effective_state = "open"

        section_items.append(
            {
                "num": item["n"],
                "title": item.get("t", ""),
                "repo": item.get("r", ""),
                "updated": item.get("u", ""),
                "created": item.get("cr", ""),
                "url": item.get("url", ""),
                "draft": item.get("d", False),
                "author": item.get("a", ""),
                "assignee": item.get("as", ""),
                "assignees": item.get("assignees") or [],
                "labels": item.get("labels") or [],
                "comments": item.get("c", 0) or 0,
                "kind": kind,
                "state": effective_state,
            }
        )
    section_items.sort(key=lambda it: str(it.get("created") or ""), reverse=True)
    result.extend(section_items)
    return result


_BACKPORT_STATUS_RE = re.compile(r"## (\U0001f494|\U0001f49a)")
_BACKPORT_ROW_RE = re.compile(
    r"\|([^|]*)\|([^|]+)\|(.+)\|",
)
_TABLE_NOISE_RE = re.compile(r"^[-:\s]+$")
_BACKPORT_PR_URL_RE = re.compile(r"github\.com/([^/]+/[^/]+)/pull/(\d+)")
_VERSION_LABEL_RE = re.compile(r"^v(\d+)\.(\d+)\.\d+$")


def _parse_backport_state(comments: list[dict[str, Any]]) -> dict[str, int | None]:
    """Parse backport comments to build per-branch state.

    Returns {branch: backport_pr_number | None}.
    None means the branch still needs a backport (failed, no PR created).
    A PR number means a backport was created for that branch.

    Later comments override earlier ones (retry scenarios).
    """
    branches: dict[str, int | None] = {}
    for comment in comments:
        body = comment.get("body", "")
        if not _BACKPORT_STATUS_RE.search(body):
            continue
        for row_m in _BACKPORT_ROW_RE.finditer(body):
            status_cell = row_m.group(1).strip()
            branch = row_m.group(2).strip()
            if branch == "Branch" or _TABLE_NOISE_RE.match(branch):
                continue
            if "\u2705" in status_cell:  # ✅
                result_cell = row_m.group(3)
                pr_m = _BACKPORT_PR_URL_RE.search(result_cell)
                branches[branch] = int(pr_m.group(2)) if pr_m else None
            elif "\u274c" in status_cell:  # ❌
                branches[branch] = None
    return branches


def _needed_branches_from_labels(labels: list[dict[str, Any]], base_ref: str) -> set[str] | None:
    """Derive expected backport target branches from current ``v<X>.<Y>.<Z>`` labels.

    Returns ``{"8.18", "8.19", ...}`` (major.minor) or ``None`` if the PR has no
    version labels (caller should skip filtering — likely a non-Kibana repo or
    a different convention).

    Excludes the branch the parent PR was already merged to: when ``base_ref``
    equals a derived branch, drop it; when ``base_ref == "main"``, drop the
    highest derived branch (Kibana convention: highest ``v*.*.*`` label maps
    to the main development branch).
    """
    branches: set[str] = set()
    for label in labels:
        name = (label.get("name") or "") if isinstance(label, dict) else ""
        m = _VERSION_LABEL_RE.match(name)
        if m:
            branches.add(f"{m.group(1)}.{m.group(2)}")
    if not branches:
        return None
    if base_ref in branches:
        branches.discard(base_ref)
    elif base_ref == "main":
        try:
            highest = max(branches, key=lambda b: tuple(int(x) for x in b.split(".")))
            branches.discard(highest)
        except (ValueError, TypeError):
            pass
    return branches


_MANUAL_BACKPORT_CHUNK = 3


def _search_manual_backports_chunk(
    parents: list[tuple[str, str, int]],
) -> dict[str, dict[str, tuple[int, str, str, str]]]:
    """Run a small batch of per-parent title-search aliases in one GraphQL call."""
    if not parents:
        return {}

    aliases: list[str] = []
    alias_to_parent: dict[str, tuple[str, str, int]] = {}
    for parent_alias, nwo, parent_num in parents:
        sa = f"_sb{parent_alias}"
        q = f'repo:{nwo} is:pr in:title \\"(#{parent_num})\\"'
        aliases.append(
            f'{sa}: search(query: "{q}", type: ISSUE, first: 20) '
            f"{{ nodes {{ ... on PullRequest {{ number title baseRefName state url }} }} }}"
        )
        alias_to_parent[sa] = (parent_alias, nwo, parent_num)

    query = "query { " + " ".join(aliases) + " }"
    try:
        result = subprocess.run(
            ["gh", "api", "graphql", "-f", f"query={query}"],
            check=False,
            capture_output=True,
            text=True,
            timeout=20,
        )
        if not result.stdout.strip():
            return {}
        data = json.loads(result.stdout).get("data", {})
    except Exception:
        return {}

    out: dict[str, dict[str, tuple[int, str, str, str]]] = {}
    for sa, (parent_alias, _nwo, parent_num) in alias_to_parent.items():
        nodes = (data.get(sa) or {}).get("nodes") or []
        for node in nodes:
            num = node.get("number")
            if not num or num == parent_num:
                continue
            base = node.get("baseRefName") or ""
            title = node.get("title") or ""
            if not base or not title.startswith(f"[{base}]"):
                continue
            state = node.get("state") or ""
            url = node.get("url") or ""
            existing = out.get(parent_alias, {}).get(base)
            if existing is None or (existing[1] != "MERGED" and state == "MERGED"):
                out.setdefault(parent_alias, {})[base] = (num, state, title, url)

    return out


def _search_manual_backports(
    parents: list[tuple[str, str, int]],
) -> dict[str, dict[str, tuple[int, str, str, str]]]:
    """Find backport PRs by title pattern for each parent.

    ``parents`` is a list of ``(alias, nwo, parent_num)``. For each parent we
    search ``repo:<nwo> is:pr in:title "(#<parent_num>)"``. A result is treated
    as a backport for ``baseRefName`` only when its title starts with
    ``[<baseRefName>]`` (Kibana convention) — this filters out unrelated PRs
    that happen to mention the parent in their title (e.g. reverts).

    Splits parents into ``_MANUAL_BACKPORT_CHUNK``-sized parallel requests for
    the same reason as ``_graphql_pr_metadata``: GitHub serialises aliases
    inside one query, so several smaller concurrent queries finish faster.

    Returns ``{alias: {branch: (pr_num, state, title, url)}}``. When multiple
    PRs target the same branch, MERGED wins over OPEN/CLOSED.
    """
    if not parents:
        return {}

    chunks = [parents[i : i + _MANUAL_BACKPORT_CHUNK] for i in range(0, len(parents), _MANUAL_BACKPORT_CHUNK)]
    workers = max(1, min(IO_FANOUT_CAP, len(chunks)))
    out: dict[str, dict[str, tuple[int, str, str, str]]] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        for chunk_out in pool.map(_search_manual_backports_chunk, chunks):
            for parent_alias, branch_map in chunk_out.items():
                target = out.setdefault(parent_alias, {})
                for branch, info in branch_map.items():
                    existing = target.get(branch)
                    if existing is None or (existing[1] != "MERGED" and info[1] == "MERGED"):
                        target[branch] = info
    return out


def fetch_backport_failures(kind: str, idx: int, title: str, filters: str, limit: int = 30) -> list[dict[str, Any]]:
    """Fetch merged PRs with incomplete backports.

    A PR is shown if any target branch either has no backport PR or has a
    backport PR that is not yet merged.
    """
    candidates = fetch_section(kind, idx, title, filters, limit=limit)
    header = (
        candidates[0]
        if (candidates and candidates[0].get("_header"))
        else {"_header": True, "kind": kind, "idx": idx, "title": title, "_fetch_error": True}
    )
    items = [i for i in candidates if not i.get("_header") and i.get("num")]
    if not items:
        return [header]

    # Phase 1: fetch comments to find backport status
    by_repo: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        by_repo.setdefault(item["repo"], []).append(item)

    aliases: list[str] = []
    alias_map: dict[str, dict[str, Any]] = {}
    for nwo, repo_items in by_repo.items():
        owner, name = nwo.split("/", 1) if "/" in nwo else ("", nwo)
        for item in repo_items:
            n = item["num"]
            alias = f"_bp{owner}_{name}_{n}".replace("-", "_")
            aliases.append(
                f'{alias}: repository(owner: "{owner}", name: "{name}") '
                f"{{ pullRequest(number: {n}) {{ number baseRefName "
                f"comments(last: 100) {{ nodes {{ body }} }} "
                f"labels(first: 50) {{ nodes {{ name }} }} }} }}"
            )
            alias_map[alias] = item

    if not aliases:
        return []

    # Phase 1: comments+labels (per parent) and manual-backport search run in
    # parallel — both only need the parent PR list, so there is no dependency
    # between them. Halves the wall-clock spent in this section's GraphQL chain.
    query = "query { " + " ".join(aliases) + " }"

    def _run_comments_labels() -> dict[str, Any]:
        try:
            r = subprocess.run(
                ["gh", "api", "graphql", "-f", f"query={query}"],
                check=False,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if not r.stdout.strip():
                return {}
            return json.loads(r.stdout).get("data", {})
        except Exception:
            return {}

    manual_parents_pre = [(alias, alias_map[alias]["repo"], alias_map[alias]["num"]) for alias in alias_map]
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as _pool:
        f_data = _pool.submit(_run_comments_labels)
        f_manual = _pool.submit(_search_manual_backports, manual_parents_pre)
        data = f_data.result()
        manual_finds_all = f_manual.result()

    if not data:
        return []

    # Build per-item backport state and collect backport PR numbers to check.
    # Filter branches by current labels: a branch whose ``v<X>.<Y>.*`` label was
    # removed is no longer a needed target (e.g. team decided not to backport).
    item_branches: dict[str, dict[str, int | None]] = {}
    bp_pr_nums: dict[str, set[int]] = {}
    for alias, item in alias_map.items():
        pr_node = (data.get(alias) or {}).get("pullRequest")
        if not pr_node:
            continue
        comments = (pr_node.get("comments") or {}).get("nodes") or []
        branches = _parse_backport_state(comments)
        if not branches:
            continue

        labels = (pr_node.get("labels") or {}).get("nodes") or []
        base_ref = pr_node.get("baseRefName") or ""
        needed = _needed_branches_from_labels(labels, base_ref)
        if needed is not None:
            branches = {b: v for b, v in branches.items() if b in needed}
            if not branches:
                continue

        item_branches[alias] = branches
        for _branch, bp_num in branches.items():
            if bp_num is not None:
                nwo = item["repo"]
                bp_pr_nums.setdefault(nwo, set()).add(bp_num)

    if not item_branches:
        return [header]

    # Phase 1.5: merge in manually-created backport PRs the bot didn't comment
    # about. The bot's tables can lag reality when retries are partial or when
    # contributors cherry-pick by hand. A PR titled ``[<branch>] ... (#<parent>)``
    # is the canonical Kibana backport; finding one for a branch the parser
    # thought was missing/unmerged means the work is actually done.
    bp_info: dict[tuple[str, int], tuple[str, str, str]] = {}  # (nwo, num) -> (state, title, url)
    manual_finds = {a: f for a, f in manual_finds_all.items() if a in item_branches}
    for alias, found in manual_finds.items():
        if alias not in item_branches:
            continue
        branches = item_branches[alias]
        nwo = alias_map[alias]["repo"]
        for branch, (mb_num, mb_state, mb_title, mb_url) in found.items():
            if branch not in branches:
                continue
            if branches[branch] != mb_num:
                branches[branch] = mb_num
            bp_info[(nwo, mb_num)] = (mb_state, mb_title, mb_url)

    # Phase 2: batch-check state for any comment-derived PR numbers we don't
    # already have from the title search.
    bp_aliases: list[str] = []
    bp_alias_map: dict[str, tuple[str, int]] = {}
    for nwo, nums in bp_pr_nums.items():
        owner, name = nwo.split("/", 1) if "/" in nwo else ("", nwo)
        for n in nums:
            if (nwo, n) in bp_info:
                continue
            alias = f"_bps{owner}_{name}_{n}".replace("-", "_")
            bp_aliases.append(
                f'{alias}: repository(owner: "{owner}", name: "{name}") '
                f"{{ pullRequest(number: {n}) {{ number state title url }} }}"
            )
            bp_alias_map[alias] = (nwo, n)

    if bp_aliases:
        bp_query = "query { " + " ".join(bp_aliases) + " }"
        try:
            bp_result = subprocess.run(
                ["gh", "api", "graphql", "-f", f"query={bp_query}"],
                check=False,
                capture_output=True,
                text=True,
                timeout=15,
            )
            if bp_result.stdout.strip():
                bp_data = json.loads(bp_result.stdout).get("data", {})
                for alias, (nwo, n) in bp_alias_map.items():
                    node = (bp_data.get(alias) or {}).get("pullRequest")
                    if node:
                        bp_info[(nwo, n)] = (
                            node.get("state", ""),
                            node.get("title", ""),
                            node.get("url", ""),
                        )
        except Exception:
            pass

    # Phase 3: filter and build grouped output (keep parent + its sub-rows together)
    grouped: list[tuple[dict[str, Any], list[dict[str, Any]]]] = []
    for alias, branches in item_branches.items():
        item = alias_map[alias]
        nwo = item["repo"]
        pending: list[tuple[str, int | None]] = []
        for branch, bp_num in branches.items():
            if bp_num is None:
                pending.append((branch, None))
            else:
                info = bp_info.get((nwo, bp_num))
                state = info[0] if info else ""
                if state != "MERGED":
                    pending.append((branch, bp_num))

        if not pending:
            continue
        parent_id = f"pr:{nwo}:{int(item['num'])}"
        subs: list[dict[str, Any]] = []
        for branch, bp_num in pending:
            if bp_num is not None:
                info = bp_info.get((nwo, bp_num))
                state = info[0] if info else "OPEN"
                bp_title = info[1] if info else ""
                bp_url = info[2] if info else f"https://github.com/{nwo}/pull/{bp_num}"
                subs.append(
                    {
                        "_backport_sub": True,
                        "_tree_role": "child",
                        "_parent_id": parent_id,
                        "_tree_branch": branch,
                        "kind": "pr",
                        "num": bp_num,
                        "repo": nwo,
                        "title": bp_title,
                        "url": bp_url,
                        "branch": branch,
                        "state": state,
                    }
                )
            else:
                subs.append(
                    {
                        "_backport_sub": True,
                        "_backport_sub_missing": True,
                        "_tree_role": "child",
                        "_parent_id": parent_id,
                        "_tree_branch": branch,
                        "kind": "pr",
                        "num": 0,
                        "repo": nwo,
                        "title": "",
                        "url": "",
                        "branch": branch,
                        "state": "MISSING",
                    }
                )
        item["_tree_role"] = "parent"
        item["_parent_id"] = ""
        grouped.append((item, subs))

    if not grouped:
        return [header]

    grouped.sort(key=lambda t: str(t[0].get("created") or ""), reverse=True)
    result_items: list[dict[str, Any]] = []
    for parent, subs in grouped:
        result_items.append(parent)
        # Keep a deterministic order for sub-rows: branch name then PR number (0 last).
        subs.sort(
            key=lambda s: (
                str(s.get("branch") or "").lower(),
                1 if int(s.get("num") or 0) == 0 else 0,
                int(s.get("num") or 0),
            )
        )
        result_items.extend(subs)

    return [header] + result_items


def _terminal_columns() -> int:
    try:
        return os.get_terminal_size().columns
    except Exception:
        return 200


def _review_badge(decision: str) -> str:
    return _review_badge2(decision, stale=False)


def _review_badge2(decision: str, stale: bool) -> str:
    d = (decision or "").upper()
    if d == "APPROVED":
        return REVIEW_APPROVED_STALE if stale else REVIEW_APPROVED
    if d == "CHANGES_REQUESTED":
        return REVIEW_CHANGES_STALE if stale else REVIEW_CHANGES
    if d == "REVIEW_REQUIRED":
        return REVIEW_PENDING_STALE if stale else REVIEW_PENDING
    return REVIEW_SPACER


def _ci_badge(state: str) -> str:
    return _ci_badge2(state, stale=False)


def _ci_badge2(state: str, stale: bool) -> str:
    s = (state or "").upper()
    if s == "SUCCESS":
        return CI_SUCCESS_STALE if stale else CI_SUCCESS
    if s in ("FAILURE", "ERROR"):
        return CI_FAILURE_STALE if stale else CI_FAILURE
    if s in ("PENDING", "EXPECTED"):
        return CI_PENDING_STALE if stale else CI_PENDING
    return CI_SPACER


def _annotate_is_last_child(items: list[dict[str, Any]]) -> None:
    """Mark `_is_last_child=True` on the final child of every (section, parent) block.

    Walks the post-`group_into_families` list in order: each header opens a new
    section bucket; consecutive children with the same `_parent_id` form a
    sibling group; the highest-index child in that group is the "last" one and
    drives the `└─` vs `├─` glyph choice in `format_lines`. Children whose
    `_parent_id` doesn't match the most recent parent in the section (orphans
    after filtering) are treated as their own group of one.
    """
    section_idx = -1
    last_by_key: dict[tuple[int, str], int] = {}
    for i, item in enumerate(items):
        if item.get("_header"):
            section_idx += 1
            continue
        if item.get("_tree_role") != "child":
            continue
        key = (section_idx, str(item.get("_parent_id", "")))
        last_by_key[key] = i
    for i, item in enumerate(items):
        if item.get("_tree_role") != "child":
            continue
    # Two-pass: now stamp each child.
    section_idx = -1
    for i, item in enumerate(items):
        if item.get("_header"):
            section_idx += 1
            continue
        if item.get("_tree_role") != "child":
            continue
        key = (section_idx, str(item.get("_parent_id", "")))
        item["_is_last_child"] = last_by_key.get(key) == i


def _tree_prefix(role: str, is_last_child: bool) -> str:
    """Return the dim tree glyph prefix for a row.

    Parents and loose rows render with no prefix — they stay aligned with the
    left edge. Children get `├─ ` for siblings and `└─ ` for the last child in
    a sibling group; the dimming keeps the glyphs visually subordinate to the
    item icons that follow.
    """
    if role != "child":
        return ""
    glyph = "└─" if is_last_child else "├─"
    return c("2;38;5;244", glyph) + " "


def format_lines(
    items: list[dict[str, Any]],
    wt_index: dict[str, dict[int, _ItemInfo]],
    prior_pr_badges: dict[tuple[str, int], tuple[str, str, str]] | None = None,
) -> list[str]:
    """Format item dicts into TSV lines for fzf, with worktree + review markers."""
    cols = _terminal_columns()
    visible = int(cols * 0.45)
    # Fixed: icon(1) + marker(1) + review(1) + ci(1) + conflict(1) + spaces(~8) + #number(~8) + repo(~17) + author(~20) + date(~6) + padding(~6)
    fixed_width = 69
    max_title = max(40, visible - fixed_width)

    _annotate_is_last_child(items)

    lines: list[str] = []
    prior = prior_pr_badges or {}
    section_title = ""
    for item in items:
        if item.get("_header"):
            section_title = str(item["title"])
            count = item.get("_count")
            count_text = f"{count} item" + ("" if count == 1 else "s") if isinstance(count, int) else ""
            scopes = ", ".join(str(v) for v in item.get("_scopes", []) if v)
            age_bits = []
            if item.get("_newest"):
                age_bits.append(f"new {item['_newest']}")
            if item.get("_oldest") and item.get("_oldest") != item.get("_newest"):
                age_bits.append(f"old {item['_oldest']}")
            family_bits: list[str] = []
            epic_count = int(item.get("_epic_count") or 0)
            family_count = int(item.get("_family_count") or 0)
            done_count = int(item.get("_done_count") or 0)
            if epic_count:
                family_bits.append(f"{epic_count} epic" + ("" if epic_count == 1 else "s"))
            if family_count:
                family_bits.append(f"{family_count} PR famil" + ("y" if family_count == 1 else "ies"))
            if done_count:
                family_bits.append(f"{done_count} sub done")
            meta_bits = [
                v
                for v in [
                    count_text,
                    " · ".join(family_bits),
                    item.get("_reason"),
                    " / ".join(age_bits),
                    scopes,
                ]
                if v
            ]
            header_text = f"── {item['title']} · {' · '.join(str(v) for v in meta_bits)} ──"
            header = c("1;38;5;244", header_text)
            # Section headers: 14 fields total. Display + "header" + "" (repo) +
            # section_id (pr:N / issue:N) + "" (url) + title (mk/search) + 8
            # empty trailing fields (meta, mergeable, section, sort_created,
            # sort_updated, parent_id, tree_role, tree_branch).
            lines.append(f"{header}\theader\t\t{item['kind']}:{item['idx']}\t\t{item['title']}\t\t\t\t\t\t\t\t")
            continue

        tree_role = str(item.get("_tree_role") or "")
        parent_id = str(item.get("_parent_id") or "")
        tree_branch = str(item.get("_tree_branch") or "")
        is_last_child = bool(item.get("_is_last_child"))
        prefix = _tree_prefix(tree_role, is_last_child)

        if item.get("_backport_sub"):
            branch = item["branch"]
            state = item["state"]
            num = item["num"]
            repo = item["repo"]
            url = item.get("url", "")
            title_text = item.get("title", "")
            if len(title_text) > max_title:
                title_text = title_text[: max_title - 1] + "…"
            arrow = c("2;38;5;244", "↳")
            branch_col = c("38;5;141", branch)
            if state == "MISSING":
                state_col = c("38;5;196", "no backport PR")
                display = f"{prefix}{arrow} {branch_col}  {state_col}"
                mk = f"{branch} backport missing {repo}"
                # MISSING placeholder keeps kind=header (non-clickable). The
                # parent_id/tree_role/tree_branch tail keeps it linked to its
                # family for sort + collapse + mark-subtree paths.
                lines.append(f"{display}\theader\t{repo}\t0\t\t{mk}\t\t\t\t\t\t{parent_id}\t{tree_role}\t{tree_branch}")
            else:
                item_info = wt_index.get(repo, {}).get(int(num))
                local_marker = ICON_LOCAL if (item_info and item_info.has_wt) else ICON_LOCAL_SPACER
                gql_known = bool(item_info and (item_info.mergeable or item_info.review or item_info.ci))
                prior_key = (repo, int(num))
                prior_review, prior_ci, prior_mergeable = prior.get(prior_key, ("", "", ""))
                review = (
                    _review_badge2(item_info.review, stale=False)
                    if (item_info and gql_known)
                    else _review_badge2(prior_review, stale=True)
                    if ((not gql_known) and prior_review)
                    else REVIEW_SPACER
                )
                ci = (
                    _ci_badge2(item_info.ci, stale=False)
                    if (item_info and gql_known)
                    else _ci_badge2(prior_ci, stale=True)
                    if ((not gql_known) and prior_ci)
                    else CI_SPACER
                )
                conflict = CONFLICT_SPACER
                mergeable_val = (
                    item_info.mergeable if (item_info and gql_known and item_info.mergeable) else ""
                ) or prior_mergeable
                if mergeable_val == "CONFLICTING" and (item_info and gql_known and item_info.mergeable):
                    conflict = CONFLICT_BADGE
                elif mergeable_val == "CONFLICTING":
                    conflict = CONFLICT_BADGE_STALE
                if state == "MERGED":
                    state_icon = ICON_PR_MERGED
                elif state == "CLOSED":
                    state_icon = ICON_PR_CLOSED
                else:
                    state_icon = ICON_PR_OPEN
                num_col = c("38;5;81", f"#{num}")
                display = (
                    f"{prefix}{state_icon} {local_marker} {review} {ci} {conflict} "
                    f"{arrow} {branch_col}  {num_col} {title_text}"
                )
                mk = f"#{num} {title_text} {repo} {branch}"
                meta_review = (item_info.review if (item_info and gql_known) else prior_review) or ""
                meta_ci = (item_info.ci if (item_info and gql_known) else prior_ci) or ""
                meta_col = f"{meta_review},{meta_ci}" if (meta_review or meta_ci) else ""
                mergeable_col = (
                    item_info.mergeable
                    if (item_info and gql_known and item_info.mergeable)
                    else (prior_mergeable or "")
                )
                sort_created = str(item.get("created") or "")
                sort_updated = str(item.get("updated") or "")
                lines.append(
                    f"{display}\tpr\t{repo}\t{num}\t{url}\t{mk}\t{meta_col}\t{mergeable_col}\t"
                    f"{section_title}\t{sort_created}\t{sort_updated}\t{parent_id}\t{tree_role}\t{tree_branch}"
                )
            continue

        kind = item["kind"]
        num = item["num"]
        repo = item["repo"]
        item_kind = "issue" if kind == "issue" else "pr"

        state = item.get("state", "open")
        if kind == "issue":
            if state == "not_planned":
                icon = ICON_ISSUE_NOT_PLANNED
            elif state == "closed":
                icon = ICON_ISSUE_CLOSED
            else:
                icon = ICON_ISSUE_OPEN
        elif item.get("draft"):
            icon = ICON_PR_DRAFT
        elif state == "merged":
            icon = ICON_PR_MERGED
        elif state == "closed":
            icon = ICON_PR_CLOSED
        else:
            icon = ICON_PR_OPEN

        # Family root icon override: epics and PR families get a distinct
        # leading glyph so the user sees the parent's role at a glance. Leaf
        # state stays accessible via the icon's color hue (open/merged/etc).
        if tree_role == "parent":
            if kind == "issue" and int(item.get("_sub_total") or 0) > 0:
                icon = ICON_EPIC
            elif kind != "issue":
                icon = ICON_PR_FAMILY

        item_info = wt_index.get(repo, {}).get(int(num))
        local_marker = ICON_LOCAL if (item_info and item_info.has_wt) else ICON_LOCAL_SPACER
        gql_known = bool(item_info and (item_info.mergeable or item_info.review or item_info.ci))
        prior_key = (repo, int(num))
        prior_review, prior_ci, prior_mergeable = prior.get(prior_key, ("", "", ""))
        review = (
            _review_badge2(item_info.review, stale=False)
            if (item_kind == "pr" and item_info and gql_known)
            else _review_badge2(prior_review, stale=True)
            if (item_kind == "pr" and (not gql_known) and prior_review)
            else REVIEW_SPACER
        )
        ci = (
            _ci_badge2(item_info.ci, stale=False)
            if (item_kind == "pr" and item_info and gql_known)
            else _ci_badge2(prior_ci, stale=True)
            if (item_kind == "pr" and (not gql_known) and prior_ci)
            else CI_SPACER
        )
        conflict = CONFLICT_SPACER
        mergeable_val = (
            item_info.mergeable if (item_info and gql_known and item_info.mergeable) else ""
        ) or prior_mergeable
        if mergeable_val == "CONFLICTING" and (item_info and gql_known and item_info.mergeable):
            conflict = CONFLICT_BADGE
        elif mergeable_val == "CONFLICTING":
            conflict = CONFLICT_BADGE_STALE

        title_text = item["title"]
        if len(title_text) > max_title:
            title_text = title_text[: max_title - 1] + "…"

        comments = item.get("comments", 0)
        comment_col = f" {COMMENT_ICON}{c('38;5;244', str(comments))}" if comments > 0 else ""

        num_col = c("38;5;81", f"#{num}")
        # Child rows dim repo + author because they almost always match the
        # parent's; keeping them full-brightness adds visual noise without
        # adding info. The leading tree glyph + parent row already anchor
        # the family identity.
        is_child = tree_role == "child"
        repo_color = "2;38;5;244" if is_child else "38;5;244"
        repo_col = c(repo_color, short_repo(repo))
        author = item.get("author", "")
        assignee = item.get("assignee", "")
        who = author
        who_extra = ""
        if item_kind == "issue":
            if assignee:
                who = f"@{assignee}"
                if author and author != assignee:
                    who_extra = c("2;38;5;244", f" (@{author})")
            else:
                who = "<unassigned>"
                if author:
                    who_extra = c("2;38;5;244", f" (@{author})")
        else:
            who = f"@{author}" if author else ""
        who_color = "2;38;5;244" if is_child else "38;5;244"
        who_col = (c(who_color, who) + who_extra) if who else c(who_color, "@—")
        date_col = c("38;5;244", relative_date(item["updated"]))

        # Epic completion badge: epics with sub-issues annotate their title
        # with `N/M done` in dim cyan. Goes inside the title-area space so
        # the column alignment stays intact for non-epic rows.
        epic_badge = ""
        if tree_role == "parent" and int(item.get("_sub_total") or 0) > 0:
            sc = int(item.get("_sub_completed") or 0)
            st = int(item.get("_sub_total") or 0)
            epic_badge = "  " + c("2;38;5;81", f"{sc}/{st} done")

        # PR \u2194 Issue cross-link badge: surfaces the closing PR on an issue
        # row (`\u21b3 #271562`) and the closed-by issue on a PR row
        # (`\u21b3 closes #239902`). One badge per row, OPEN partner preferred.
        # Suppressed on a child whose parent already IS the cross-link partner
        # (avoids redundancy when same-section nesting has run): the parent
        # row directly above already shows the partner identity via the tree.
        cross_badge = ""
        link = item.get("_cross_link")
        if link:
            partner_kind, partner_repo_link, partner_num, partner_state = link
            partner_state = (partner_state or "").upper()
            partner_open = partner_state == "OPEN"
            link_color = "2;38;5;81" if partner_open else "2;38;5;244"
            suppress_badge = (
                tree_role == "child" and item.get("_parent_id") == f"{partner_kind}:{partner_repo_link}:{partner_num}"
            )
            if not suppress_badge:
                if partner_kind == "pr":
                    cross_badge = "  " + c(link_color, f"\u21b3 #{partner_num}")
                elif partner_kind == "issue":
                    cross_badge = "  " + c(link_color, f"\u21b3 closes #{partner_num}")

        display = (
            f"{prefix}{icon} {local_marker} {review} {ci} {conflict} {num_col} {title_text}{epic_badge}{cross_badge}"
            f"  {repo_col}  {who_col}  {date_col}{comment_col}"
        )
        labels = item.get("labels") or []
        assignees = item.get("assignees") or []
        signals = [
            item_kind,
            f"state:{state}",
            "local" if (item_info and item_info.has_wt) else "",
            f"review:{(item_info.review if (item_info and gql_known) else prior_review) or ''}",
            f"ci:{(item_info.ci if (item_info and gql_known) else prior_ci) or ''}",
            f"mergeable:{mergeable_val}" if mergeable_val else "",
            "conflict" if mergeable_val == "CONFLICTING" else "",
            "draft" if item.get("draft") else "",
        ]
        if link:
            partner_kind, _partner_repo, partner_num, _partner_state = link
            signals.append("linked")
            if partner_kind == "pr" and item_kind == "issue":
                signals.append(f"closed-by:{partner_num}")
            elif partner_kind == "issue" and item_kind == "pr":
                signals.append(f"closes:{partner_num}")
        mk = _search_blob(
            f"#{num}",
            title_text,
            repo,
            short_repo(repo),
            who,
            f"@{author}",
            f"@{assignee}",
            assignees,
            labels,
            signals,
            "<unassigned>",
        )
        # Preserve last-known review/ci if GraphQL is missing so badges don't
        # disappear on the next refresh.
        meta_review = (item_info.review if (item_info and gql_known) else prior_review) or ""
        meta_ci = (item_info.ci if (item_info and gql_known) else prior_ci) or ""
        meta_col = f"{meta_review},{meta_ci}" if (meta_review or meta_ci) else ""
        mergeable_col = (
            item_info.mergeable if (item_info and gql_known and item_info.mergeable) else (prior_mergeable or "")
        )
        sort_created = str(item.get("created") or "")
        sort_updated = str(item.get("updated") or "")
        lines.append(
            f"{display}\t{item_kind}\t{repo}\t{num}\t{item['url']}\t{mk}\t{meta_col}\t{mergeable_col}\t"
            f"{section_title}\t{sort_created}\t{sort_updated}\t{parent_id}\t{tree_role}\t{tree_branch}"
        )

    return lines


def _atomic_write_text(path: str, text: str) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp_name = ""
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            delete=False,
            dir=str(p.parent),
            prefix=f".{p.name}.",
            suffix=".tmp",
        ) as f:
            tmp_name = f.name
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_name, str(p))
        tmp_name = ""
    finally:
        if tmp_name:
            try:
                os.unlink(tmp_name)
            except Exception:
                pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", default="work")
    parser.add_argument("--config", required=True)
    parser.add_argument("--cache-file", required=True)
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--scope", default=os.environ.get("GH_PICKER_SCOPE", "all"))
    parser.add_argument("--filter-cache", action="store_true")
    args = parser.parse_args()

    scope = str(args.scope or "all")
    cache_dir = str(Path(args.cache_file).parent)
    sort_key = _read_sort_key(cache_dir)

    collapsed = _read_collapsed_set(cache_dir, args.mode)

    if args.filter_cache:
        # Cache-only render path (the instant `start:reload(cache-only)` open).
        # The cached rows already encode their section/scope, so we only need
        # the parsed config for scope filtering, and only when a non-`all`
        # scope is active. Parsing unconditionally here means every picker
        # open shells out to `yq`; under restore-time CPU/IO contention that
        # `yq` call can exceed parse_config's 5s timeout, and its "Failed to
        # parse config" stderr leaks into the fzf popup even though the config
        # is not actually needed to render the cache. Defer the parse so the
        # common `scope=all` open never touches `yq`.
        scope_map: dict[str, set[str]] = {}
        effective_scope = scope
        if scope and scope != "all":
            pr_sections, issue_sections, _repo_paths = parse_config(args.config)
            if pr_sections or issue_sections:
                scope_map = _section_scope_map(pr_sections, issue_sections)
            else:
                # Cache-only is a best-effort first paint. If the narrowed-scope
                # config parse fails, keep showing the cached dashboard instead
                # of filtering every section out with an empty scope map.
                effective_scope = "all"
        try:
            raw = Path(args.cache_file).read_text(encoding="utf-8", errors="replace")
        except Exception:
            return
        lines = raw.splitlines()
        filtered = _filter_lines_for_scope(lines, effective_scope, scope_map)
        sorted_lines = _sort_within_sections(filtered, sort_key)
        collapsed_lines = _apply_collapsed_state(sorted_lines, collapsed)
        _write_offsets(cache_dir, args.mode, scope, collapsed_lines)
        output = "\n".join(collapsed_lines)
        if output.strip():
            sys.stdout.write(output + "\n")
            sys.stdout.flush()
        return

    # Full-fetch path genuinely needs the parsed sections.
    pr_sections, issue_sections, repo_paths = parse_config(args.config)
    scope_map = _section_scope_map(pr_sections, issue_sections)

    prior_pr_badges = _read_prior_pr_badges(args.cache_file)
    linked_issues = _linked_issue_numbers_from_pick_session_cache()
    viewer_login = _current_login()

    all_lines: list[str] = []

    tasks: list[tuple[str, int, str, str, str, list[str]]] = []
    for i, s in enumerate(pr_sections):
        tasks.append(("pr", i, s["title"], s["filters"], s.get("source", ""), list(s.get("scopes", []))))
    for i, s in enumerate(issue_sections):
        tasks.append(("issue", i, s["title"], s["filters"], "", list(s.get("scopes", []))))

    if not tasks:
        return

    _SOURCE_FETCHERS = {
        "backport-failures": fetch_backport_failures,
    }

    # Phase 1: fetch all sections concurrently
    results: dict[int, list[dict[str, Any]]] = {}
    section_workers = max(1, min(IO_FANOUT_CAP, len(tasks)))
    with concurrent.futures.ThreadPoolExecutor(max_workers=section_workers) as pool:
        section_futs: dict[concurrent.futures.Future[list[dict[str, Any]]], int] = {}
        for task_idx, (kind, idx, title, filters, source, _scopes) in enumerate(tasks):
            fetcher = _SOURCE_FETCHERS.get(source, fetch_section)
            if fetcher is fetch_section:
                fut = pool.submit(fetcher, kind, idx, title, filters, 30, viewer_login)
            else:
                fut = pool.submit(fetcher, kind, idx, title, filters)
            section_futs[fut] = task_idx

        for fut in concurrent.futures.as_completed(section_futs):
            task_idx = section_futs[fut]
            try:
                sec = fut.result()
            except Exception:
                sec = []
            if sec and sec[0].get("_header"):
                _kind, _idx, _title, filters, source, scopes = tasks[task_idx]
                sec[0]["_scopes"] = scopes
                sec[0]["_reason"] = _section_reason(filters, source)
            results[task_idx] = sec

    errored_sections: set[str] = set()
    for task_idx in sorted(results.keys()):
        sec = results.get(task_idx) or []
        if sec and sec[0].get("_header"):
            if sec[0].get("_fetch_error"):
                errored_sections.add(f"{sec[0].get('kind')}:{sec[0].get('idx')}")

    all_items: list[dict[str, Any]] = []
    seen_items: set[tuple[str, str, str]] = set()
    wt_repos: set[str] = set()
    pr_nums_by_repo: dict[str, set[int]] = {}
    issue_nums_by_repo: dict[str, set[int]] = {}
    for task_idx in sorted(results.keys()):
        for item in results[task_idx]:
            if item.get("_header"):
                all_items.append(item)
                continue
            if item.get("_backport_sub"):
                all_items.append(item)
                repo = item.get("repo") or ""
                if repo:
                    wt_repos.add(str(repo))
                    try:
                        num = int(item.get("num") or 0)
                    except Exception:
                        num = 0
                    if num > 0:
                        pr_nums_by_repo.setdefault(str(repo), set()).add(num)
                continue

            k = str(item.get("kind") or "")
            r = str(item.get("repo") or "")
            n = str(item.get("num") or "")
            if k and r and n:
                key = (k, r, n)
                if key in seen_items:
                    continue
                seen_items.add(key)

            all_items.append(item)
            if not item.get("_header") and item.get("repo"):
                wt_repos.add(item["repo"])
                if item.get("kind") == "pr":
                    pr_nums_by_repo.setdefault(item["repo"], set()).add(int(item["num"]))
                elif item.get("kind") == "issue":
                    try:
                        issue_nums_by_repo.setdefault(item["repo"], set()).add(int(item["num"]))
                    except (ValueError, TypeError):
                        pass

    # Phase 2: local worktree scan + GraphQL review data (concurrent)
    resolved_repos: dict[str, str] = {}
    for nwo in wt_repos:
        local = resolve_repo_path(nwo, repo_paths)
        if local:
            resolved_repos[nwo] = local

    local_data: dict[str, tuple[set[int], set[str], dict[int, str]]] = {}
    gql_data: dict[str, dict[int, tuple]] = {}
    issue_meta: dict[str, dict[int, tuple]] = {}

    phase2_workers = max(1, min(IO_FANOUT_CAP, len(resolved_repos) + 2))
    with concurrent.futures.ThreadPoolExecutor(max_workers=phase2_workers) as pool:
        wt_futs: dict[concurrent.futures.Future[tuple[set[int], set[str], dict[int, str]]], str] = {}
        for nwo, path in resolved_repos.items():
            fut = pool.submit(_scan_local_worktrees, nwo, path)
            wt_futs[fut] = nwo

        gql_fut = pool.submit(_graphql_pr_metadata, pr_nums_by_repo) if pr_nums_by_repo else None
        issue_fut = pool.submit(_graphql_issue_metadata, issue_nums_by_repo) if issue_nums_by_repo else None

        for fut in concurrent.futures.as_completed(wt_futs):
            nwo = wt_futs[fut]
            try:
                local_data[nwo] = fut.result()
            except Exception:
                pass

        if gql_fut is not None:
            try:
                gql_data = gql_fut.result()
            except Exception:
                pass

        if issue_fut is not None:
            try:
                issue_meta = issue_fut.result()
            except Exception:
                pass

    wt_index: dict[str, dict[int, _ItemInfo]] = {}
    all_nwos = set(local_data.keys()) | set(gql_data.keys())
    all_nwos |= set(linked_issues.keys())
    for nwo in all_nwos:
        wt_nums, branches, branch_num_source = local_data.get(nwo, (set(), set(), {}))
        # Include issue numbers linked from the sessions/worktrees picker cache.
        wt_nums |= linked_issues.get(nwo, set())
        gql_prs = gql_data.get(nwo, {})
        info: dict[int, _ItemInfo] = {}

        for n in wt_nums:
            info[n] = _ItemInfo(has_wt=True)

        # Build suffix index for fork-PR detection: ,w prs names fork branches
        # as <remote>__<headRefName>, so a PR's headRefName won't match directly.
        branch_heads: set[str] = set()
        for b in branches:
            dunder = b.find("__")
            if dunder >= 0:
                branch_heads.add(b[dunder + 2 :])

        # Track which branches are claimed by a PR via GraphQL head matching,
        # so we can remove false-positive wt_nums extracted from those branches.
        claimed_branches: set[str] = set()

        for num, meta in gql_prs.items():
            head = meta[0]
            review = meta[1]
            ci = meta[2]
            mergeable = meta[3]
            has_local = head in branches or head in branch_heads or num in wt_nums
            if has_local and head in branches:
                claimed_branches.add(head)
            if num in info:
                info[num].review = review
                info[num].ci = ci
                info[num].mergeable = mergeable
                info[num].has_wt = info[num].has_wt or has_local
            elif has_local or review or ci or mergeable:
                info[num] = _ItemInfo(has_wt=has_local, review=review, ci=ci, mergeable=mergeable)

        # Remove false-positive has_wt for numbers extracted from a branch
        # that is actually the headRef of a different PR.  Example: branch
        # `backport/9.3/pr-258942` belongs to PR 260061 — the regex extracts
        # 258942, but that number is the parent PR, not a local worktree.
        #
        # Issue numbers are exempt: a branch like `feature-name-239902` is the
        # worktree for issue #239902 and may also be the headRef of the PR
        # that closes the issue (e.g. PR #271562). Stripping has_wt from the
        # issue in that case is wrong — both the issue and the PR live in the
        # same worktree.
        known_issues = issue_nums_by_repo.get(nwo, set()) | linked_issues.get(nwo, set())
        branch_to_pr: dict[str, int] = {meta[0]: num for num, meta in gql_prs.items() if meta[0] in claimed_branches}
        for n, src_branch in branch_num_source.items():
            if n in known_issues:
                continue
            owning_pr = branch_to_pr.get(src_branch)
            if owning_pr is not None and owning_pr != n:
                entry = info.get(n)
                if entry and entry.has_wt and not entry.review and not entry.ci and not entry.mergeable:
                    del info[n]
                elif entry:
                    entry.has_wt = False

        if info:
            wt_index[nwo] = info

    # Detect PR backport families across all sections (Maintenance pre-groups
    # itself and is left alone). This mutates `all_items` to reorder children
    # under their parents and to inject phantom parents when the merged parent
    # is not in any section.
    _group_pr_families(all_items, gql_data)
    # Detect issue epic families. Runs after PR grouping so a section that
    # already got tree_roles from `_group_pr_families` is skipped (a single
    # section can in principle hold both PRs and issues but `_group_*` keep
    # to their own kind).
    _group_issue_families(all_items, issue_meta)
    # PR \u2194 Issue cross-linking. `_attach_cross_links` annotates every item
    # with its best partner so `format_lines` can render the inline badge;
    # `_group_cross_link_pairs` then promotes any same-section, both-loose
    # pair into a parent/child nesting (issue parent, PR child).
    _attach_cross_links(all_items, gql_data, issue_meta)
    _group_cross_link_pairs(all_items)

    _annotate_section_counts(all_items)
    all_lines = format_lines(all_items, wt_index, prior_pr_badges=prior_pr_badges)

    if errored_sections:
        prior_sections = _read_prior_sections(args.cache_file)
        if prior_sections:
            merged: list[str] = []
            cur_id = ""
            cur_lines: list[str] = []
            ordered_sections: list[tuple[str, list[str]]] = []
            for line in all_lines:
                parts = line.split("\t")
                if len(parts) >= 4 and parts[1] == "header":
                    if cur_id:
                        ordered_sections.append((cur_id, cur_lines))
                    cur_id = parts[3].strip()
                    cur_lines = [line]
                else:
                    if cur_id:
                        cur_lines.append(line)
            if cur_id:
                ordered_sections.append((cur_id, cur_lines))

            for sid, lines in ordered_sections:
                if sid in errored_sections and sid in prior_sections:
                    merged.extend(prior_sections[sid])
                else:
                    merged.extend(lines)
            all_lines = merged

    cache_output = "\n".join(all_lines)
    if cache_output.strip():
        try:
            _atomic_write_text(args.cache_file, cache_output + "\n")
        except Exception:
            pass

    filtered = _filter_lines_for_scope(all_lines, scope, scope_map)
    sorted_lines = _sort_within_sections(filtered, sort_key)
    collapsed_lines = _apply_collapsed_state(sorted_lines, collapsed)
    _write_offsets(cache_dir, args.mode, scope, collapsed_lines)
    output = "\n".join(collapsed_lines)
    sys.stdout.write(output + "\n")
    sys.stdout.flush()


if __name__ == "__main__":
    main()
