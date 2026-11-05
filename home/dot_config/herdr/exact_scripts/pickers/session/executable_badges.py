#!/usr/bin/env python3
"""Report sidebar badge tokens ($dirty, $pr, $review, $ci) for herdr workspaces.

Targets the workspace id in argv[1], else the workspace of a workspace.focused
plugin event, else every workspace. PR/review/CI come from the session
picker's GitHub cache, so this never calls `gh`.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

CACHE = (
    Path(os.environ.get("XDG_CACHE_HOME", os.path.expanduser("~/.cache"))) / "herdr-pickers" / "pick_session_gh.json"
)
REVIEW = {"APPROVED": "approved", "CHANGES_REQUESTED": "changes", "REVIEW_REQUIRED": "review"}
CI = {"SUCCESS": "✓", "FAILURE": "✗", "ERROR": "✗", "PENDING": "…", "EXPECTED": "…"}


def run(*args: str) -> str:
    return subprocess.run(args, check=False, capture_output=True, text=True).stdout


def target_id() -> str:
    if len(sys.argv) > 1 and sys.argv[1]:
        return sys.argv[1]
    try:
        return json.loads(os.environ.get("HERDR_PLUGIN_EVENT_JSON", "null") or "null")["data"]["workspace_id"]
    except (TypeError, KeyError, ValueError):
        return ""


def tokens_for(path: str, cache: dict) -> dict[str, str]:
    tokens = {"dirty": "", "pr": "", "review": "", "ci": ""}
    if not path or not os.path.isdir(path):
        return tokens
    if run("git", "-C", path, "status", "--porcelain", "--untracked-files=no").strip():
        tokens["dirty"] = "∗"
    entry = cache.get(os.path.realpath(path)) or cache.get(path) or {}
    branch = run("git", "-C", path, "symbolic-ref", "--quiet", "--short", "HEAD").strip()
    pr = entry.get("pr") if entry.get("branch") == branch else None
    if pr and pr.get("state") == "OPEN":
        tokens["pr"] = f"#{pr.get('number')}"
        tokens["review"] = REVIEW.get(pr.get("review") or "", "")
        tokens["ci"] = CI.get(pr.get("ci") or "", "")
    return tokens


def main() -> int:
    try:
        cache = json.loads(CACHE.read_text(encoding="utf-8")).get("entries", {})
    except (OSError, ValueError):
        cache = {}
    want = target_id()
    rows = run("bash", "-c", '. "$HOME/.config/herdr/scripts/pickers/lib/herdr_ws.sh"; _comma_w_workspace_list')
    for row in rows.splitlines():
        label, path, ws_id, _ = (row.split("\t") + ["", "", "", ""])[:4]
        if not ws_id or (want and ws_id != want):
            continue
        args = ["herdr", "workspace", "report-metadata", ws_id, "--source", "k18-badges"]
        for name, value in tokens_for(path, cache).items():
            args += ["--token", f"{name}={value}"] if value else ["--clear-token", name]
        subprocess.run(args, check=False, capture_output=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
