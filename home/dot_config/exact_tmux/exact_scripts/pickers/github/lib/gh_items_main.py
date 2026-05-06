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
import signal
import subprocess
import sys
import tempfile
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

    # Never show green when the rollup is failing. This prevents a single
    # "canonical" success context (e.g. kibana-ci) from masking other failing
    # required checks.
    overall_state = (rollup.get("state") or "").upper()
    if overall_state in ("FAILURE", "ERROR"):
        return "FAILURE"

    contexts = []
    try:
        contexts = (rollup.get("contexts") or {}).get("nodes") or []
    except (AttributeError, TypeError):
        pass

    if not contexts:
        return rollup.get("state", "")

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
        name = ctx.get("context", "") or ctx.get("name", "")
        if typename == "StatusContext" and _TRIVIAL_STATUS_RE.search(name):
            continue
        if typename == "CheckRun" and _TRIVIAL_CHECK_RE.search(name):
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


def _graphql_pr_metadata_chunk(items: list[tuple[str, int]]) -> dict[str, dict[int, tuple[str, str, str, str]]]:
    """Fetch metadata for a small batch of (nwo, number) pairs.

    Kept tight (≈5 PRs) because GitHub GraphQL evaluates aliases mostly
    serially per request: many small parallel calls beat one large batch.
    """
    aliases: list[str] = []
    alias_map: dict[str, tuple[str, int]] = {}
    for nwo, n in items:
        owner, name = nwo.split("/", 1) if "/" in nwo else ("", nwo)
        alias = f"_p{owner}_{name}_{n}".replace("-", "_")
        aliases.append(
            f'{alias}: repository(owner: "{owner}", name: "{name}") '
            f"{{ pullRequest(number: {n}) {{ number headRefName reviewDecision mergeable "
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

    out: dict[str, dict[int, tuple[str, str, str, str]]] = {}
    for alias, (nwo, num) in alias_map.items():
        node = (data.get(alias) or {}).get("pullRequest")
        if not node:
            continue
        head = node.get("headRefName", "")
        review = node.get("reviewDecision", "")
        mergeable = node.get("mergeable", "")
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
        out.setdefault(nwo, {})[num] = (head, review, ci_state, mergeable)

    return out


def _graphql_pr_metadata(pr_numbers: dict[str, set[int]]) -> dict[str, dict[int, tuple[str, str, str, str]]]:
    """Batch-fetch headRefName, reviewDecision, CI status, and mergeable for known PR numbers.

    Splits the work into ``_PR_METADATA_CHUNK``-sized parallel requests.
    GitHub's GraphQL evaluates aliases mostly serially within one request, so
    many small concurrent requests finish in ~1/Nth of the wall-clock that a
    single large batch would take.

    Returns:
        {nwo: {number: (headRefName, reviewDecision, ciState, mergeable), ...}}
    """
    pairs: list[tuple[str, int]] = []
    for nwo, nums in pr_numbers.items():
        for n in nums:
            pairs.append((nwo, n))
    if not pairs:
        return {}

    chunks = [pairs[i : i + _PR_METADATA_CHUNK] for i in range(0, len(pairs), _PR_METADATA_CHUNK)]
    workers = max(1, min(IO_FANOUT_CAP, len(chunks)))
    out: dict[str, dict[int, tuple[str, str, str, str]]] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        for chunk_out in pool.map(_graphql_pr_metadata_chunk, chunks):
            for nwo, num_map in chunk_out.items():
                out.setdefault(nwo, {}).update(num_map)
    return out


def parse_config(config_path: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, str]]:
    """Parse gh-dash YAML config using yq. Returns (pr_sections, issue_sections, repo_paths)."""
    pr_sections: list[dict[str, Any]] = []
    issue_sections: list[dict[str, Any]] = []
    repo_paths: dict[str, str] = {}

    try:
        raw = subprocess.run(
            ["yq", "-o", "json", ".", config_path],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        ).stdout
        data = json.loads(raw)
    except Exception as e:
        print(f"Failed to parse config: {e}", file=sys.stderr)
        return [], [], {}

    for s in data.get("prSections") or []:
        title = s.get("title", "")
        filters = s.get("filters", "")
        if title and filters:
            entry: dict[str, Any] = {"title": title, "filters": filters.strip()}
            if s.get("source"):
                entry["source"] = s["source"]
            pr_sections.append(entry)

    for s in data.get("issuesSections") or []:
        title = s.get("title", "")
        filters = s.get("filters", "")
        if title and filters:
            issue_sections.append({"title": title, "filters": filters.strip()})

    for k, v in (data.get("repoPaths") or {}).items():
        repo_paths[str(k)] = str(v)

    return pr_sections, issue_sections, repo_paths


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


def fetch_section(kind: str, idx: int, title: str, filters: str, limit: int = 30) -> list[dict[str, Any]]:
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
                        "kind": "pr",
                        "num": 0,
                        "repo": nwo,
                        "title": "",
                        "url": "",
                        "branch": branch,
                        "state": "MISSING",
                    }
                )
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

    lines: list[str] = []
    prior = prior_pr_badges or {}
    for item in items:
        if item.get("_header"):
            header = c("1;38;5;244", f"── {item['title']} ──")
            lines.append(f"{header}\theader\t\t{item['kind']}:{item['idx']}\t\t{item['title']}\t\t")
            continue

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
                display = f"{arrow} {branch_col}  {state_col}"
                mk = f"{branch} backport missing {repo}"
                lines.append(f"{display}\theader\t{repo}\t0\t\t{mk}\t\t")
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
                    f"{state_icon} {local_marker} {review} {ci} {conflict} {arrow} {branch_col}  {num_col} {title_text}"
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
                lines.append(f"{display}\tpr\t{repo}\t{num}\t{url}\t{mk}\t{meta_col}\t{mergeable_col}")
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
        repo_col = c("38;5;244", short_repo(repo))
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
        who_col = (c("38;5;244", who) + who_extra) if who else c("38;5;244", "@—")
        date_col = c("38;5;244", relative_date(item["updated"]))

        display = f"{icon} {local_marker} {review} {ci} {conflict} {num_col} {title_text}  {repo_col}  {who_col}  {date_col}{comment_col}"
        mk = f"#{num} {title_text} {repo} {who} @{author} @{assignee} <unassigned>"
        # Preserve last-known review/ci if GraphQL is missing so badges don't
        # disappear on the next refresh.
        meta_review = (item_info.review if (item_info and gql_known) else prior_review) or ""
        meta_ci = (item_info.ci if (item_info and gql_known) else prior_ci) or ""
        meta_col = f"{meta_review},{meta_ci}" if (meta_review or meta_ci) else ""
        mergeable_col = (
            item_info.mergeable if (item_info and gql_known and item_info.mergeable) else (prior_mergeable or "")
        )
        lines.append(f"{display}\t{item_kind}\t{repo}\t{num}\t{item['url']}\t{mk}\t{meta_col}\t{mergeable_col}")

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
    args = parser.parse_args()

    pr_sections, issue_sections, repo_paths = parse_config(args.config)
    prior_pr_badges = _read_prior_pr_badges(args.cache_file)
    linked_issues = _linked_issue_numbers_from_pick_session_cache()

    all_lines: list[str] = []

    tasks: list[tuple[str, int, str, str, str]] = []
    for i, s in enumerate(pr_sections):
        tasks.append(("pr", i, s["title"], s["filters"], s.get("source", "")))
    for i, s in enumerate(issue_sections):
        tasks.append(("issue", i, s["title"], s["filters"], ""))

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
        for task_idx, (kind, idx, title, filters, source) in enumerate(tasks):
            fetcher = _SOURCE_FETCHERS.get(source, fetch_section)
            fut = pool.submit(fetcher, kind, idx, title, filters)
            section_futs[fut] = task_idx

        for fut in concurrent.futures.as_completed(section_futs):
            task_idx = section_futs[fut]
            try:
                results[task_idx] = fut.result()
            except Exception:
                results[task_idx] = []

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

    # Phase 2: local worktree scan + GraphQL review data (concurrent)
    resolved_repos: dict[str, str] = {}
    for nwo in wt_repos:
        local = resolve_repo_path(nwo, repo_paths)
        if local:
            resolved_repos[nwo] = local

    local_data: dict[str, tuple[set[int], set[str], dict[int, str]]] = {}
    gql_data: dict[str, dict[int, tuple[str, str, str, str]]] = {}

    phase2_workers = max(1, min(IO_FANOUT_CAP, len(resolved_repos) + 1))
    with concurrent.futures.ThreadPoolExecutor(max_workers=phase2_workers) as pool:
        wt_futs: dict[concurrent.futures.Future[tuple[set[int], set[str], dict[int, str]]], str] = {}
        for nwo, path in resolved_repos.items():
            fut = pool.submit(_scan_local_worktrees, nwo, path)
            wt_futs[fut] = nwo

        gql_fut = pool.submit(_graphql_pr_metadata, pr_nums_by_repo) if pr_nums_by_repo else None

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

        for num, (head, review, ci, mergeable) in gql_prs.items():
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
        branch_to_pr: dict[str, int] = {head: num for num, (head, *_) in gql_prs.items() if head in claimed_branches}
        for n, src_branch in branch_num_source.items():
            owning_pr = branch_to_pr.get(src_branch)
            if owning_pr is not None and owning_pr != n:
                entry = info.get(n)
                if entry and entry.has_wt and not entry.review and not entry.ci and not entry.mergeable:
                    del info[n]
                elif entry:
                    entry.has_wt = False

        if info:
            wt_index[nwo] = info

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

    output = "\n".join(all_lines)
    if output.strip():
        try:
            _atomic_write_text(args.cache_file, output + "\n")
        except Exception:
            pass

    sys.stdout.write(output + "\n")
    sys.stdout.flush()


if __name__ == "__main__":
    main()
