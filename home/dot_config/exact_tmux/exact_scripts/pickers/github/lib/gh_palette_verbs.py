#!/usr/bin/env python3
"""Command-palette verbs for the GitHub picker.

Each subcommand wraps a single `gh` CLI invocation against the current cursor
item. Stdlib only — no PyGithub, no requests. The orchestrator
(`gh_picker_palette.sh`) shells out to this module after the user picks a verb
and provides arguments.

Conventions:
- Every verb accepts `--kind`, `--repo`, `--num` so the orchestrator can pass
  the cursor item fields without parsing them in shell.
- Verbs that require additional arguments accept them as explicit flags so
  shell quoting stays simple (`--body`, `--reason`, `--name`, `--user`).
- On success, exit code is 0 and the human-friendly result line goes to
  stdout. On failure, the captured `gh` stderr goes to stderr and exit code
  is non-zero so the orchestrator can surface it via `tmux display-message`.
- Some verbs only apply to PRs (`approve`, `request-changes`, `merge`, `rr`).
  Calling those with `--kind issue` exits non-zero with a clear message.

The `label-completions` and `reviewer-completions` subcommands are read-only
helpers used by the orchestrator's fzf arg prompts; they print one candidate
per line on stdout.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from typing import Sequence

PR_ONLY = {"approve", "request-changes", "merge", "rr"}
CLOSE_REASONS = ("completed", "not planned", "duplicate")


def _run_gh(args: Sequence[str]) -> tuple[int, str, str]:
    try:
        proc = subprocess.run(
            ["gh", *args],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return proc.returncode, proc.stdout, proc.stderr
    except FileNotFoundError:
        return 127, "", "gh CLI not found"
    except subprocess.TimeoutExpired:
        return 124, "", "gh CLI timed out"


def _require_pr(verb: str, kind: str) -> None:
    if verb in PR_ONLY and kind != "pr":
        print(f"{verb}: only valid on PRs (got kind={kind})", file=sys.stderr)
        sys.exit(2)


def verb_close(args: argparse.Namespace) -> int:
    base = ["issue" if args.kind == "issue" else "pr", "close", str(args.num), "-R", args.repo]
    if args.kind == "issue" and args.reason:
        base.extend(["-r", args.reason])
    rc, out, err = _run_gh(base)
    sys.stderr.write(err)
    if rc == 0:
        print(f"closed {args.kind} {args.repo}#{args.num}")
    return rc


def verb_reopen(args: argparse.Namespace) -> int:
    base = ["issue" if args.kind == "issue" else "pr", "reopen", str(args.num), "-R", args.repo]
    rc, out, err = _run_gh(base)
    sys.stderr.write(err)
    if rc == 0:
        print(f"reopened {args.kind} {args.repo}#{args.num}")
    return rc


def verb_approve(args: argparse.Namespace) -> int:
    _require_pr("approve", args.kind)
    rc, out, err = _run_gh(["pr", "review", str(args.num), "-R", args.repo, "--approve"])
    sys.stderr.write(err)
    if rc == 0:
        print(f"approved pr {args.repo}#{args.num}")
    return rc


def verb_request_changes(args: argparse.Namespace) -> int:
    _require_pr("request-changes", args.kind)
    if not args.body:
        print("request-changes: --body is required", file=sys.stderr)
        return 2
    rc, out, err = _run_gh(
        [
            "pr",
            "review",
            str(args.num),
            "-R",
            args.repo,
            "--request-changes",
            "--body",
            args.body,
        ]
    )
    sys.stderr.write(err)
    if rc == 0:
        print(f"requested changes on pr {args.repo}#{args.num}")
    return rc


def verb_merge(args: argparse.Namespace) -> int:
    _require_pr("merge", args.kind)
    rc, out, err = _run_gh(["pr", "merge", str(args.num), "-R", args.repo])
    sys.stderr.write(err)
    if rc == 0:
        print(f"merged pr {args.repo}#{args.num}")
    return rc


def verb_label_add(args: argparse.Namespace) -> int:
    if not args.name:
        print("label-add: --name is required", file=sys.stderr)
        return 2
    kind_word = "issue" if args.kind == "issue" else "pr"
    rc, out, err = _run_gh([kind_word, "edit", str(args.num), "-R", args.repo, "--add-label", args.name])
    sys.stderr.write(err)
    if rc == 0:
        print(f"added label '{args.name}' to {args.kind} {args.repo}#{args.num}")
    return rc


def verb_label_rm(args: argparse.Namespace) -> int:
    if not args.name:
        print("label-rm: --name is required", file=sys.stderr)
        return 2
    kind_word = "issue" if args.kind == "issue" else "pr"
    rc, out, err = _run_gh([kind_word, "edit", str(args.num), "-R", args.repo, "--remove-label", args.name])
    sys.stderr.write(err)
    if rc == 0:
        print(f"removed label '{args.name}' from {args.kind} {args.repo}#{args.num}")
    return rc


def verb_comment(args: argparse.Namespace) -> int:
    if not args.body:
        print("comment: --body is required", file=sys.stderr)
        return 2
    kind_word = "issue" if args.kind == "issue" else "pr"
    rc, out, err = _run_gh([kind_word, "comment", str(args.num), "-R", args.repo, "--body", args.body])
    sys.stderr.write(err)
    if rc == 0:
        print(f"commented on {args.kind} {args.repo}#{args.num}")
    return rc


def verb_rr(args: argparse.Namespace) -> int:
    _require_pr("rr", args.kind)
    if not args.user:
        print("rr: --user is required", file=sys.stderr)
        return 2
    user = args.user.lstrip("@")
    rc, out, err = _run_gh(
        [
            "pr",
            "edit",
            str(args.num),
            "-R",
            args.repo,
            "--add-reviewer",
            user,
        ]
    )
    sys.stderr.write(err)
    if rc == 0:
        print(f"requested review from @{user} on pr {args.repo}#{args.num}")
    return rc


def verb_label_completions(args: argparse.Namespace) -> int:
    rc, out, err = _run_gh(["label", "list", "-R", args.repo, "--limit", "500", "--json", "name"])
    if rc != 0:
        sys.stderr.write(err)
        return rc
    try:
        labels = json.loads(out)
    except json.JSONDecodeError:
        return 0
    for entry in labels:
        name = entry.get("name") if isinstance(entry, dict) else None
        if isinstance(name, str) and name:
            print(name)
    return 0


def verb_current_labels(args: argparse.Namespace) -> int:
    kind_word = "issue" if args.kind == "issue" else "pr"
    rc, out, err = _run_gh([kind_word, "view", str(args.num), "-R", args.repo, "--json", "labels"])
    if rc != 0:
        sys.stderr.write(err)
        return rc
    try:
        payload = json.loads(out)
    except json.JSONDecodeError:
        return 0
    for entry in payload.get("labels", []) or []:
        if isinstance(entry, dict):
            name = entry.get("name")
            if isinstance(name, str) and name:
                print(name)
    return 0


def verb_reviewer_completions(args: argparse.Namespace) -> int:
    rc, out, err = _run_gh(
        [
            "api",
            f"repos/{args.repo}/collaborators",
            "--paginate",
            "--jq",
            ".[].login",
        ]
    )
    if rc != 0:
        sys.stderr.write(err)
        return rc
    for line in out.splitlines():
        login = line.strip()
        if login:
            print(login)
    return 0


def verb_close_reasons(_args: argparse.Namespace) -> int:
    for reason in CLOSE_REASONS:
        print(reason)
    return 0


def _add_common(p: argparse.ArgumentParser) -> None:
    p.add_argument("--kind", required=True, choices=["pr", "issue"])
    p.add_argument("--repo", required=True)
    p.add_argument("--num", required=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="verb", required=True)

    p = sub.add_parser("close")
    _add_common(p)
    p.add_argument("--reason", default="")
    p.set_defaults(func=verb_close)

    p = sub.add_parser("reopen")
    _add_common(p)
    p.set_defaults(func=verb_reopen)

    p = sub.add_parser("approve")
    _add_common(p)
    p.set_defaults(func=verb_approve)

    p = sub.add_parser("request-changes")
    _add_common(p)
    p.add_argument("--body", required=True)
    p.set_defaults(func=verb_request_changes)

    p = sub.add_parser("merge")
    _add_common(p)
    p.set_defaults(func=verb_merge)

    p = sub.add_parser("label-add")
    _add_common(p)
    p.add_argument("--name", required=True)
    p.set_defaults(func=verb_label_add)

    p = sub.add_parser("label-rm")
    _add_common(p)
    p.add_argument("--name", required=True)
    p.set_defaults(func=verb_label_rm)

    p = sub.add_parser("comment")
    _add_common(p)
    p.add_argument("--body", required=True)
    p.set_defaults(func=verb_comment)

    p = sub.add_parser("rr")
    _add_common(p)
    p.add_argument("--user", required=True)
    p.set_defaults(func=verb_rr)

    p = sub.add_parser("label-completions")
    p.add_argument("--repo", required=True)
    p.set_defaults(func=verb_label_completions)

    p = sub.add_parser("current-labels")
    _add_common(p)
    p.set_defaults(func=verb_current_labels)

    p = sub.add_parser("reviewer-completions")
    p.add_argument("--repo", required=True)
    p.set_defaults(func=verb_reviewer_completions)

    p = sub.add_parser("close-reasons")
    p.set_defaults(func=verb_close_reasons)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
