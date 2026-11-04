#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import pty
import select
import subprocess
import sys
import tempfile
import termios
import time
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


class SubissueInputTests(unittest.TestCase):
    def test_quoted_milestone_passes_interactive_validation_and_session_values_round_trip(self) -> None:
        output, saved, _, _ = self._run_creator("milestone")
        self.assertIn('ID:  #101 - Title: Release "A"', output)
        self.assertEqual(saved["milestone_title"], 'Release "A"')
        self.assertEqual(saved["label"], 'area "A"\\path')

    def test_recent_issue_on_later_page_is_reused_without_creation(self) -> None:
        for scenario in ("issue", "issue-pr"):
            with self.subTest(scenario=scenario):
                output, _, calls, _ = self._run_creator(scenario)
                self.assertFalse(any("POST" in call for call in calls), calls)
                self.assertIn("already exists as #401", output)
                self.assertIn("#401 - Issue title", output)

    def test_missing_label_lists_choices_from_later_pages(self) -> None:
        output, saved, _, _ = self._run_creator("label")
        self.assertIn("later-page-label", output)
        self.assertEqual(saved["label"], "")

    def test_failed_duplicate_lookup_does_not_create_an_issue(self) -> None:
        _, _, calls, status = self._run_creator("issue-failure")
        self.assertFalse(any("POST" in call for call in calls), calls)
        self.assertNotEqual(status, 0)

    def test_pull_request_parent_is_rejected_before_creation(self) -> None:
        _, saved, calls, status = self._run_creator("parent-pr")
        self.assertFalse(any("POST" in call for call in calls), calls)
        self.assertNotEqual(status, 0)
        self.assertEqual(saved, {})

        _, saved, calls, status = self._run_creator("parent-issue")
        self.assertEqual(sum("POST" in call for call in calls), 1, calls)
        self.assertTrue(any("childIssueId=I_999" in call for call in calls), calls)
        self.assertEqual(saved["parent_issue"], "1")
        self.assertEqual(status, 0)

    def _run_creator(self, scenario: str) -> tuple[str, dict, list[list[str]], int]:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bin_dir = root / "bin"
            bin_dir.mkdir()
            title = 'Release "A"'
            label = 'area "A"\\path'
            milestone_pages = [[{"title": title, "number": 101}]]
            if scenario == "milestone":
                milestone_pages.insert(0, [{"title": f"Milestone {i}", "number": i} for i in range(1, 101)])
            fixture = {
                "milestones": milestone_pages,
                "issues": [
                    [{"title": f"Other issue {i}", "number": i} for i in range(100)],
                    [{"title": "Issue title", "number": 401}],
                ],
                "labels": [[{"name": f"label-{i}"} for i in range(30)], [{"name": "later-page-label"}]],
                "missing_label": scenario == "label",
                "failed_issue_page": scenario == "issue-failure",
                "parent_is_pr": scenario == "parent-pr",
            }
            if scenario in ("parent-pr", "parent-issue"):
                fixture["issues"] = [[]]
            if scenario == "issue-pr":
                fixture["issues"][0][50] = {"title": "Issue title", "number": 50, "pull_request": {"url": "unused"}}
            (root / "fixture.json").write_text(json.dumps(fixture))
            gh = bin_dir / "gh"
            gh.write_text(
                f"#!{sys.executable}\n"
                + """import json, os, subprocess, sys
from pathlib import Path
root = Path(os.environ["CREATOR_FIXTURE"])
args = sys.argv[1:]
with (root / "api-calls.jsonl").open("a") as log:
    log.write(json.dumps(args) + "\\n")
fixture = json.loads((root / "fixture.json").read_text())
endpoint = next((arg for arg in args if arg.startswith("repos/")), "")
pages = [{}]
if "--method" in args and args[args.index("--method") + 1] == "POST":
    pages = [{"number": 999}]
elif endpoint.endswith("/issues/1"):
    pages = [{"number": 1}]
    if fixture["parent_is_pr"]:
        pages[0]["pull_request"] = {"url": "https://api.github.com/repos/owner/repo/pulls/1"}
elif "milestones?" in endpoint:
    pages = fixture["milestones"]
elif "issues?" in endpoint:
    pages = fixture["issues"]
    if fixture["failed_issue_page"]:
        pages = pages[:1]
elif "/labels/" in endpoint and fixture["missing_label"]:
    sys.exit(1)
elif endpoint.endswith("/labels"):
    pages = fixture["labels"]
elif "graphql" in args:
    number = next((arg.split("=", 1)[1] for arg in args if arg.startswith("number=")), "")
    pages = [{"data": {"node": {"subIssues": {"nodes": [{"id": "I_401"}]}},
                       "repository": {"issue": {"id": "I_" + number}}}}]
if "--paginate" not in args:
    pages = pages[:1]
for page in pages:
    if "--jq" in args:
        query = args[args.index("--jq") + 1]
        result = subprocess.run(["jq", "-r", query], input=json.dumps(page), text=True, check=True, capture_output=True)
        print(result.stdout, end="")
    else:
        print(json.dumps(page))
if "issues?" in endpoint and fixture["failed_issue_page"]:
    print("fixture next page failed", file=sys.stderr)
    sys.exit(1)
"""
            )
            gh.chmod(0o755)
            editor = bin_dir / "editor"
            editor.write_text('#!/bin/sh\nprintf "Issue title\\nIssue body\\n" > "$1"\n')
            editor.chmod(0o755)
            source = REPO / "home/exact_lib/exact_,gh-subissues-create/main.sh"
            command = root / "main.sh"
            original_session = 'SESSION_FILE="/tmp/github-sub-issue-creator-session.json"'
            self.assertEqual(source.read_text().count(original_session), 1)
            command.write_text(source.read_text().replace(original_session, f'SESSION_FILE="{root}/session.json"'))
            env = {
                **os.environ,
                "HOME": str(root),
                "PATH": f"{bin_dir}:{os.environ['PATH']}",
                "EDITOR": str(editor),
                "CREATOR_FIXTURE": str(root),
                "TERM": "xterm",
            }
            master, slave = pty.openpty()
            output = bytearray()
            steps = [
                (b"GitHub Owner/Organization: ", "owner", True),
                (b"Repository Name: ", "repo", True),
                (b"Parent Issue Number: ", "1", True),
            ]
            if scenario == "milestone":
                steps.append((b"Milestone (title): ", "missing milestone", True))
            steps.extend(
                [
                    (b"Milestone (title): ", title, True),
                    (b"Label: ", label, True),
                    (b"Press Enter to continue...", "", False),
                    (b"Is this correct? (y/n) [y]: ", "", True),
                    (
                        b"Proceed with creation? (y/n) [y]: ",
                        "y" if scenario.startswith(("issue", "parent-")) else "n",
                        True,
                    ),
                ]
            )
            try:
                process = subprocess.Popen(["bash", str(command)], stdin=slave, stdout=slave, stderr=slave, env=env)
                os.close(slave)
                slave = -1
                deadline = time.monotonic() + 10
                next_step = 0
                consumed = 0
                cancelled_parent = False
                try:
                    while process.poll() is None:
                        if time.monotonic() >= deadline:
                            self.fail(f"creator could not finish {scenario}: {output.decode(errors='replace')}")
                        if scenario == "parent-pr" and next_step > 2 and not cancelled_parent:
                            retry = output.find(b"Parent Issue Number: ", consumed)
                            if retry >= 0 and not (termios.tcgetattr(master)[3] & termios.ICANON):
                                os.write(master, b"\x04")
                                cancelled_parent = True
                        if next_step < len(steps):
                            prompt, response, readline = steps[next_step]
                            terminal_ready = not readline or not (termios.tcgetattr(master)[3] & termios.ICANON)
                            position = output.find(prompt, consumed)
                            if position >= 0 and terminal_ready:
                                os.write(master, (response + "\n").encode())
                                consumed = position + len(prompt)
                                next_step += 1
                        readable, _, _ = select.select([master], [], [], 0.01)
                        if readable:
                            try:
                                block = os.read(master, 65536)
                            except OSError:
                                break
                            if not block:
                                break
                            output.extend(block)
                    process.wait(timeout=max(0.01, deadline - time.monotonic()))
                finally:
                    if process.poll() is None:
                        process.kill()
                        process.wait(timeout=2)
            finally:
                os.close(master)
                if slave >= 0:
                    os.close(slave)
            if scenario not in ("issue-failure", "parent-pr"):
                self.assertEqual(process.returncode, 0, output.decode(errors="replace"))
            session = root / "session.json"
            saved = json.loads(session.read_text()) if session.exists() else {}
            if scenario != "parent-pr":
                self.assertEqual(
                    {key: saved[key] for key in ("owner", "repo", "parent_issue")},
                    {"owner": "owner", "repo": "repo", "parent_issue": "1"},
                )
            calls = [json.loads(line) for line in (root / "api-calls.jsonl").read_text().splitlines()]
            return output.decode(errors="replace"), saved, calls, process.returncode
