#!/usr/bin/env python3
"""Read-only PR readiness + body-vs-diff audit for elastic/kibana PRs.

Reports drift before a reply/resolve/push cycle. Never mutates GitHub: it
prints findings so the human acts. See the Human-Visible Publication Gate (SOP, ~/AGENTS.md).

Checks:
  - local HEAD vs remote branch vs PR headRefOid alignment
  - unresolved review threads, split human vs bot (feeds Drain Mode)
  - deleted files/exports disclosed in the PR body
  - expected body sections present (Summary / Test Plan / Root Cause / Release Note)
  - label consistency (single release_note:*, backport target, body<->label agreement)
  - validation commands recorded in the Test Plan (check_changes / type_check)

Usage:
  ,kbn-pr-audit [<pr-number|url|branch>]   # defaults to the current branch's PR
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys

KNOWN_BOTS = {"elasticmachine", "kibanamachine", "github-actions[bot]", "kibana-ci"}

GREEN, YELLOW, RED, DIM, RST = "\033[32m", "\033[33m", "\033[31m", "\033[2m", "\033[0m"
PASS, WARN, FAIL = f"{GREEN}PASS{RST}", f"{YELLOW}WARN{RST}", f"{RED}FAIL{RST}"


def _env() -> dict:
    env = dict(os.environ)
    env["GH_PAGER"] = "cat"
    return env


def run(cmd: list[str], check: bool = False) -> tuple[int, str]:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, env=_env(), check=False, timeout=60)
    except (OSError, subprocess.TimeoutExpired) as exc:
        if check:
            raise SystemExit(f"command failed: {' '.join(cmd)}: {exc}")
        return 1, ""
    if check and p.returncode != 0:
        raise SystemExit(f"command failed: {' '.join(cmd)}\n{p.stderr.strip()}")
    return p.returncode, p.stdout.strip()


def gh_json(args: list[str]) -> dict | list:
    _, out = run(["gh", *args], check=True)
    return json.loads(out) if out else {}


def resolve_pr(target: str | None) -> str:
    if target:
        rc, out = run(["gh", "pr", "view", target, "--json", "number", "--jq", ".number"])
        if rc == 0 and out:
            return out
    rc, out = run([os.path.expanduser("~/bin/,gh-prw"), "--number"])
    if rc == 0 and out.strip().isdigit():
        return out.strip()
    raise SystemExit("could not resolve PR; pass a PR number/URL/branch explicitly")


def author_is_bot(login: str, typename: str) -> bool:
    return typename == "Bot" or login.endswith("[bot]") or login in KNOWN_BOTS


def fetch_threads(owner: str, repo: str, number: str) -> list[dict]:
    query = (
        "query($owner:String!,$repo:String!,$number:Int!){"
        "repository(owner:$owner,name:$repo){pullRequest(number:$number){"
        "reviewThreads(first:100){nodes{isResolved isOutdated "
        "comments(first:1){nodes{author{login __typename}}}}}}}}"
    )
    rc, out = run(
        [
            "gh",
            "api",
            "graphql",
            "-f",
            f"owner={owner}",
            "-f",
            f"repo={repo}",
            "-F",
            f"number={number}",
            "-f",
            f"query={query}",
        ]
    )
    if rc != 0 or not out:
        return []
    nodes = (
        json.loads(out)
        .get("data", {})
        .get("repository", {})
        .get("pullRequest", {})
        .get("reviewThreads", {})
        .get("nodes", [])
    )
    return nodes or []


def deleted_paths(base: str) -> list[str]:
    for ref in (f"origin/{base}", f"upstream/{base}", base):
        rc, mb = run(["git", "merge-base", ref, "HEAD"])
        if rc == 0 and mb:
            _, out = run(["git", "diff", "--diff-filter=D", "--name-only", mb, "HEAD"])
            return [l for l in out.splitlines() if l.strip()]
    return []


def line(status: str, label: str, detail: str = "") -> tuple[str, str]:
    print(f"  {status}  {label}" + (f"  {DIM}{detail}{RST}" if detail else ""))
    return status, label


def main(argv: list[str]) -> int:
    target = argv[0] if argv else None
    if not os.path.isdir(".git") and run(["git", "rev-parse", "--is-inside-work-tree"])[0] != 0:
        raise SystemExit("not inside a git repo")

    nwo = (gh_json(["repo", "view", "--json", "nameWithOwner"]) or {}).get("nameWithOwner", "")
    owner, _, repo = str(nwo).partition("/")
    number = resolve_pr(target)

    pr = gh_json(
        [
            "pr",
            "view",
            number,
            "--json",
            "headRefOid,headRefName,baseRefName,isDraft,mergeable,mergeStateStatus,body,labels,title",
        ]
    )
    body = pr.get("body") or ""
    labels = [l["name"] for l in pr.get("labels", [])]
    base = pr.get("baseRefName") or "main"
    head_ref = pr.get("headRefName") or ""

    print(f"\n{DIM},kbn-pr-audit{RST} {owner}/{repo} PR #{number} — {pr.get('title', '')}")
    print(
        f"  {DIM}base={base} head={head_ref} draft={pr.get('isDraft')} "
        f"mergeable={pr.get('mergeable')}/{pr.get('mergeStateStatus')}{RST}\n"
    )

    results: list[str] = []

    # 1. HEAD alignment (local vs the authoritative published PR head)
    local_head = run(["git", "rev-parse", "HEAD"])[1]
    pr_head = pr.get("headRefOid") or ""
    if local_head and pr_head and local_head == pr_head:
        results.append(line(PASS, "branch alignment", f"local==PR head {local_head[:9]}")[0])
    else:
        results.append(
            line(
                FAIL,
                "branch alignment",
                f"local={local_head[:9]} != PR head={pr_head[:9]} (git fetch origin {head_ref})",
            )[0]
        )

    # 2. unresolved threads (human vs bot)
    threads = fetch_threads(owner, repo, number)
    human = bot = 0
    for t in threads:
        if t.get("isResolved"):
            continue
        cnodes = t.get("comments", {}).get("nodes", [])
        author = (cnodes[0].get("author") or {}) if cnodes else {}
        if author_is_bot(author.get("login", ""), author.get("__typename", "")):
            bot += 1
        else:
            human += 1
    if human == 0 and bot == 0:
        results.append(line(PASS, "review threads", "none unresolved")[0])
    else:
        st = WARN if human else PASS
        results.append(line(st, "review threads", f"{human} human (supervised) / {bot} bot (drainable)")[0])

    # 3. deletions disclosed
    deleted = deleted_paths(base)
    if deleted:
        disclosed = bool(re.search(r"remov|delet|obsolete|drop", body, re.I))
        st = PASS if disclosed else WARN
        results.append(
            line(
                st,
                "deletions disclosed",
                f"{len(deleted)} file(s) deleted; body {'mentions' if disclosed else 'silent on'} removals",
            )[0]
        )
    else:
        line(PASS, "deletions disclosed", "no file deletions")

    # 4. body sections
    has = lambda s: bool(re.search(rf"(?mi)^##\s+{s}\b", body))
    missing = [s for s in ("Summary", "Test Plan") if not has(s)]
    rn_label = [l for l in labels if l.startswith("release_note:")]
    wants_rn = any(l in ("release_note:fix", "release_note:feature") for l in rn_label)
    if wants_rn and not has("Release Note"):
        missing.append("Release Note")
    if missing:
        results.append(line(WARN, "body sections", "missing: " + ", ".join(missing))[0])
    else:
        results.append(line(PASS, "body sections", "Summary/Test Plan present")[0])

    # 5. label consistency
    backport = [l for l in labels if l.startswith("backport:")]
    label_issues = []
    if len(rn_label) != 1:
        label_issues.append(f"release_note labels={rn_label or 'none'}")
    if not backport:
        label_issues.append("no backport label")
    if has("Release Note") and not wants_rn:
        label_issues.append("body has Release Note but label is not fix/feature")
    if label_issues:
        results.append(line(WARN, "labels", "; ".join(label_issues))[0])
    else:
        results.append(line(PASS, "labels", f"{rn_label[0]}, {', '.join(backport)}")[0])

    # 6. validation commands in test plan (kibana)
    if "elastic/kibana" in nwo:
        plan = body.lower()
        miss_cmd = [c for c in ("check_changes", "type_check") if c not in plan]
        if miss_cmd:
            results.append(line(WARN, "validation recorded", "test plan missing: " + ", ".join(miss_cmd))[0])
        else:
            results.append(line(PASS, "validation recorded", "check_changes + type_check cited")[0])

    fails = sum(1 for r in results if "FAIL" in r)
    warns = sum(1 for r in results if "WARN" in r)
    print(
        f"\n  {DIM}summary:{RST} {len(results)} checks, "
        f"{RED if fails else DIM}{fails} fail{RST}, {YELLOW if warns else DIM}{warns} warn{RST}\n"
    )
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
