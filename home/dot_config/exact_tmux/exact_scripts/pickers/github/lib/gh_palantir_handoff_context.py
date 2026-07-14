#!/usr/bin/env python3
"""Build a palantir handoff pin and context file from GitHub picker rows."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
MAX_ENRICHED_ITEMS = 12


def clean_text(value: str) -> str:
    return value.replace("\t", " ").replace("\r", " ").replace("\n", " ").strip()


def strip_ansi(value: str) -> str:
    return ANSI_RE.sub("", value)


def run_json(args: list[str], timeout: int = 10) -> dict[str, Any]:
    try:
        proc = subprocess.run(args, check=False, capture_output=True, text=True, timeout=timeout)
    except Exception:
        return {}
    if proc.returncode != 0 or not proc.stdout.strip():
        return {}
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def read_rows(selection_file: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    try:
        raw = Path(selection_file).read_text(encoding="utf-8", errors="replace")
    except Exception:
        return rows

    seen: set[tuple[str, str, str]] = set()
    for line in raw.splitlines():
        parts = line.split("\t")
        if len(parts) < 5:
            continue
        display, kind, repo, num, url = parts[:5]
        if kind == "header" or kind not in ("pr", "issue"):
            continue
        key = (kind, repo, num)
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "display": clean_text(strip_ansi(display)),
                "kind": kind,
                "repo": repo,
                "num": num,
                "url": url,
            }
        )
    return rows


def item_title(row: dict[str, str], data: dict[str, Any]) -> str:
    title = data.get("title")
    if isinstance(title, str) and title.strip():
        return clean_text(title)
    display = row.get("display", "")
    marker = f"#{row.get('num', '')}"
    if marker in display:
        return clean_text(display.split(marker, 1)[1])
    return marker


def repo_ref(node: dict[str, Any]) -> str:
    repo = node.get("repository") or {}
    owner = repo.get("owner") or {}
    owner_login = owner.get("login") or ""
    repo_name = repo.get("name") or ""
    number = node.get("number")
    if owner_login and repo_name and number:
        return f"{owner_login}/{repo_name}#{number}"
    if number:
        return f"#{number}"
    return ""


def enrich(row: dict[str, str]) -> dict[str, Any]:
    kind = row["kind"]
    repo = row["repo"]
    num = row["num"]
    if kind == "pr":
        data = run_json(
            [
                "gh",
                "pr",
                "view",
                num,
                "-R",
                repo,
                "--json",
                "number,title,url,state,isDraft,author,labels,reviewDecision,mergeable,headRefName,baseRefName,closingIssuesReferences",
            ]
        )
    else:
        data = run_json(
            [
                "gh",
                "issue",
                "view",
                num,
                "-R",
                repo,
                "--json",
                "number,title,url,state,stateReason,author,labels,assignees,milestone,closedByPullRequestsReferences",
            ]
        )
    data["_title"] = item_title(row, data)
    return data


def render_item(row: dict[str, str], data: dict[str, Any], enriched: bool) -> str:
    kind = row["kind"]
    ref = f"{row['repo']}#{row['num']}"
    title = data.get("_title") or row.get("display") or ref
    url = data.get("url") or row.get("url")
    out = [f"## {kind.upper()} {ref}: {title}", ""]
    if url:
        out.append(f"- URL: {url}")
    if not enriched:
        out.append("- Metadata: compact row only; enrichment cap reached or GitHub lookup failed.")
        out.append("")
        out.append(f"```text\n{row.get('display', '')}\n```")
        return "\n".join(out)

    state = data.get("state") or ""
    author = (data.get("author") or {}).get("login") or ""
    labels = [v.get("name") for v in (data.get("labels") or []) if isinstance(v, dict) and v.get("name")]
    if state:
        out.append(f"- State: {state}")
    if author:
        out.append(f"- Author: @{author}")
    if labels:
        out.append(f"- Labels: {', '.join(labels)}")

    if kind == "pr":
        branch = f"{data.get('headRefName') or ''} -> {data.get('baseRefName') or ''}".strip()
        if branch != "->":
            out.append(f"- Branch: {branch}")
        if data.get("reviewDecision"):
            out.append(f"- Review: {data['reviewDecision']}")
        if data.get("mergeable"):
            out.append(f"- Mergeable: {data['mergeable']}")
        refs = [repo_ref(v) for v in (data.get("closingIssuesReferences") or []) if isinstance(v, dict)]
        refs = [v for v in refs if v]
        if refs:
            out.append(f"- Closes: {', '.join(refs)}")
    else:
        assignees = [v.get("login") for v in (data.get("assignees") or []) if isinstance(v, dict) and v.get("login")]
        if assignees:
            out.append(f"- Assignees: {', '.join('@' + v for v in assignees)}")
        milestone = data.get("milestone") or {}
        if isinstance(milestone, dict) and milestone.get("title"):
            out.append(f"- Milestone: {milestone['title']}")
        if data.get("stateReason"):
            out.append(f"- State reason: {data['stateReason']}")
        refs = [repo_ref(v) for v in (data.get("closedByPullRequestsReferences") or []) if isinstance(v, dict)]
        refs = [v for v in refs if v]
        if refs:
            out.append(f"- Closed by: {', '.join(refs)}")

    return "\n".join(out)


def render_context(rows: list[dict[str, str]]) -> tuple[str, str, str]:
    if not rows:
        return "", "", ""

    rendered: list[str] = [
        "# GitHub Dashboard Selection",
        "",
        "This context was generated from the tmux GitHub picker for a palantir handoff.",
        "",
    ]
    titles: list[str] = []
    for idx, row in enumerate(rows):
        enriched = idx < MAX_ENRICHED_ITEMS
        data = enrich(row) if enriched else {}
        if not data:
            enriched = False
            data = {"_title": item_title(row, {})}
        title = str(data.get("_title") or f"{row['kind']} {row['repo']}#{row['num']}")
        titles.append(clean_text(title))
        rendered.append(render_item(row, data, enriched))
        rendered.append("")

    first = rows[0]
    if len(rows) == 1:
        seed = f"{first['kind']} {first['repo']}#{first['num']}: {titles[0]}"
    else:
        seed = f"selected GitHub items ({len(rows)}): " + "; ".join(
            f"{row['kind']} {row['repo']}#{row['num']}" for row in rows[:5]
        )
        if len(rows) > 5:
            seed += f"; +{len(rows) - 5} more"
    return "\n".join(rendered).rstrip() + "\n", seed, titles[0]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("selection_file")
    parser.add_argument("pin_file")
    parser.add_argument("--workspace", default=os.getcwd())
    args = parser.parse_args()

    rows = read_rows(args.selection_file)
    if not rows:
        return 0

    context, seed, first_title = render_context(rows)
    pin_path = Path(args.pin_file)
    context_file = pin_path.with_suffix(pin_path.suffix + ".context.md")
    context_file.write_text(context, encoding="utf-8")

    first = rows[0]
    fields = [
        first["kind"],
        first["repo"],
        first["num"],
        first["url"],
        first_title,
        args.workspace,
        str(context_file),
        seed,
        str(len(rows)),
    ]
    pin_path.write_text("\t".join(clean_text(v) for v in fields) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
