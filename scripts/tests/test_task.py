#!/usr/bin/env python3
"""Tests for the `,task` intent card command and its harness hooks."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
COMMAND = REPO / "home" / "exact_lib" / "exact_,task" / "main.py"

CARD = """Goal: Add the export button
Reading: The user wants CSV export on the report page.
Done when:
- the button downloads a CSV
- 1. tests cover the export
Scope: src/, tests/*.py
Not doing: PDF export
"""


class TestTask(unittest.TestCase):
    """WHEN agents keep an intent card and harness hooks check work against it."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.store = base / "store"
        self.repo = base / "work"
        self.repo.mkdir()
        self.proof = base / "proof.txt"
        self.proof.write_text("readme\n")
        self.env = {k: v for k, v in os.environ.items() if k != "AGENT_TASK_SESSION" and not k.startswith("GIT_CONFIG")}
        self.env.update(
            AGENT_TASK_DIR=str(self.store),
            CLAUDE_CONFIG_DIR=str(base / "claude"),
            GIT_CEILING_DIRECTORIES=self.tmp.name,
            GIT_CONFIG_GLOBAL=os.devnull,
            GIT_CONFIG_NOSYSTEM="1",
        )
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True, env=self.env)
        (self.repo / "README.md").write_text("readme\n")
        subprocess.run(["git", "-C", str(self.repo), "add", "."], check=True, env=self.env)
        subprocess.run(
            ["git", "-C", str(self.repo), "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "init"],
            check=True,
            env=self.env,
        )

    def tearDown(self):
        self.tmp.cleanup()

    def run_task(self, *args: str, stdin: str = "", cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(COMMAND), *args],
            input=stdin,
            capture_output=True,
            text=True,
            cwd=cwd or self.repo,
            env=self.env,
        )

    def hook(self, event: str, **data) -> dict:
        data.setdefault("session", "s1")
        data.setdefault("cwd", str(self.repo))
        result = self.run_task("hook", event, "--harness", "test", "--input", json.dumps(data))
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def set_card(self, text: str = CARD) -> subprocess.CompletedProcess[str]:
        self.hook("prompt", text="add an export button")
        return self.run_task("card", "set", stdin=text)

    def test_WHEN_review_starts_SHOULD_keep_an_acceptance_snapshot(self):
        self.set_card()

        actual = self.run_task("review", "--session", "s1")

        self.assertEqual(actual.returncode, 0, actual.stderr)
        baseline = json.loads(actual.stdout)[0]
        self.assertEqual(baseline["version"], 1)
        self.assertEqual(baseline["acceptance"]["goal"], "Add the export button")
        self.assertEqual(
            baseline["acceptance"]["done"],
            [{"id": "D1", "text": "the button downloads a CSV"}, {"id": "D2", "text": "tests cover the export"}],
        )
        stored = json.loads(self.run_task("card", "show", "--json").stdout)
        self.assertEqual(stored["reviews"], [baseline])

    def test_WHEN_only_completion_changes_SHOULD_reuse_the_review_version(self):
        self.set_card()
        baseline = self.run_task("review").stdout
        self.mark("D1")
        self.run_task("block", "D2", "--reason", "waiting for a dependency")

        actual = self.run_task("review")

        self.assertEqual(actual.returncode, 0, actual.stderr)
        self.assertEqual(json.loads(actual.stdout), json.loads(baseline))

    def test_WHEN_acceptance_changes_without_a_reason_SHOULD_preserve_the_baseline(self):
        self.set_card()
        baseline = json.loads(self.run_task("review").stdout)
        self.run_task("card", "set", stdin=CARD.replace("the button downloads a CSV", "the button downloads XLSX"))

        actual = self.run_task("review", "--reason", " ")

        self.assertEqual(actual.returncode, 1, actual.stderr)
        self.assertIn("review acceptance changed", actual.stderr)
        stored = json.loads(self.run_task("card", "show", "--json").stdout)
        self.assertEqual(stored["reviews"], baseline)

    def test_WHEN_a_revision_has_a_reason_SHOULD_keep_both_meanings_of_D1(self):
        self.set_card()
        self.run_task("review")
        self.run_task("card", "set", stdin=CARD.replace("the button downloads a CSV", "the button downloads XLSX"))

        actual = self.run_task("review", "--reason", "User changed the requested export format to XLSX")

        self.assertEqual(actual.returncode, 0, actual.stderr)
        versions = json.loads(actual.stdout)
        self.assertEqual(len(versions), 2)
        self.assertEqual(versions[0]["acceptance"]["done"][0], {"id": "D1", "text": "the button downloads a CSV"})
        self.assertEqual(versions[1]["version"], 2)
        self.assertEqual(versions[1]["acceptance"]["done"][0], {"id": "D1", "text": "the button downloads XLSX"})
        self.assertEqual(versions[1]["reason"], "User changed the requested export format to XLSX")

    def test_WHEN_scope_changes_SHOULD_require_an_explicit_review_revision(self):
        self.set_card()
        self.run_task("review")
        self.run_task("scope", "add", "éxport/link", "--reason", "A preserved caller needs the fix")

        actual = self.run_task("review")

        self.assertEqual(actual.returncode, 1, actual.stderr)
        self.assertIn("--reason", actual.stderr)

    def test_WHEN_the_goal_changes_SHOULD_keep_the_previous_review_contract(self):
        self.set_card()
        baseline = json.loads(self.run_task("review").stdout)
        self.run_task("card", "set", stdin=CARD.replace("Add the export button", "Add the import button"))

        actual = self.run_task("review")

        self.assertEqual(actual.returncode, 1, actual.stderr)
        stored = json.loads(self.run_task("card", "show", "--json").stdout)
        self.assertEqual(stored["reviews"], baseline)

    def test_WHEN_a_card_is_cleared_SHOULD_start_review_history_again(self):
        self.set_card()
        self.run_task("review")
        self.run_task("card", "clear", "--session", "s1")
        self.run_task("card", "set", "--session", "s1", stdin=CARD)

        actual = self.run_task("review", "--session", "s1")

        self.assertEqual(actual.returncode, 0, actual.stderr)
        self.assertEqual(len(json.loads(actual.stdout)), 1)
        self.assertEqual(json.loads(actual.stdout)[0]["version"], 1)

    def test_WHEN_sessions_share_a_worktree_SHOULD_keep_review_histories_separate(self):
        self.set_card()
        self.run_task("review", "--session", "s1")
        self.hook("prompt", session="s2", text="another task")
        self.run_task("card", "set", "--session", "s2", stdin=CARD.replace("export button", "import button"))

        actual = self.run_task("review", "--session", "s2")

        self.assertEqual(actual.returncode, 0, actual.stderr)
        self.assertEqual(len(json.loads(actual.stdout)), 1)
        self.assertEqual(json.loads(actual.stdout)[0]["acceptance"]["goal"], "Add the import button")
        first = json.loads(self.run_task("card", "show", "--json", "--session", "s1").stdout)
        self.assertEqual(first["reviews"][0]["acceptance"]["goal"], "Add the export button")

    def claim(self, text="README contains readme", session="s1"):
        result = self.run_task(
            "claim",
            "add",
            text,
            "--file",
            f"{self.proof}:1",
            "--text",
            "readme",
            "--session",
            session,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)["id"]

    def mark(self, item, text="ran it", session="s1"):
        claim = self.claim(text, session)
        return self.run_task("check", item, "--claim", claim, "--session", session)

    def transcript_row(self, role, content, *, origin=None, stamp=None, **fields):
        path = Path(self.env["CLAUDE_CONFIG_DIR"]) / "projects" / "fixture" / "s1.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        previous = [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []
        row = {
            "type": role,
            "sessionId": "s1",
            "uuid": f"row-{len(previous)}",
            "parentUuid": previous[-1]["uuid"] if previous else None,
            "timestamp": stamp or datetime.now(timezone.utc).isoformat(),
            "message": {"content": content},
        }
        if origin:
            row["origin"] = {"kind": origin}
        row.update(fields)
        with path.open("a") as stream:
            stream.write(json.dumps(row) + "\n")
        return row["uuid"]

    def tool_output(self, output, stamp=None, *, tool="Bash", tool_input=None):
        self.transcript_row(
            "assistant",
            [
                {
                    "type": "tool_use",
                    "id": "probe",
                    "name": tool,
                    "input": tool_input if tool_input is not None else {"command": "timeout 10 verify-fixture"},
                }
            ],
            stamp=stamp,
        )
        self.transcript_row(
            "user",
            [{"type": "tool_result", "tool_use_id": "probe", "content": output}],
            stamp=stamp,
        )

    def test_SHOULD_verify_a_long_tool_quote_without_accepting_chat_as_evidence(self):
        self.set_card()
        self.transcript_row("user", "invented proof", origin="human")
        self.transcript_row("assistant", "invented proof")
        self.tool_output("prefix" * 2000 + "the result is 17" + "suffix" * 2000)
        actual = self.run_task("claim", "add", "result is 17", "--quote", "the result is 17")
        self.assertEqual(actual.returncode, 0, actual.stderr)
        self.assertEqual(self.run_task("check", "D1", "--claim", "C1").returncode, 0)
        refused = self.run_task("claim", "add", "invented", "--quote", "invented proof")
        self.assertNotEqual(refused.returncode, 0)

    def test_SHOULD_keep_read_tool_results_without_accepting_shell_ledger_echoes(self):
        self.set_card()
        cases = [
            ("Bash", {"command": "cat source.py", "description": "Read ,task source"}, True),
            ("Bash", {"command": "rg -e -- --pre=/nonexistent/probe_ledger,task fixture"}, False),
            ("Read", {"file_path": "/home/u/lib/,task/main.py"}, True),
            ("Grep", {"pattern": ",task", "path": "docs"}, True),
            ("Glob", {"pattern": "**/,task/*.py"}, True),
            ("Bash", {"command": "cat /home/u/lib/,task/main.py"}, False),
            ("Bash", {"command": "rg ',task' card"}, False),
            ("Bash", {"command": "rg ';' ~/bin/,task"}, False),
            ("Bash", {"command": "rg '|' ~/bin/,task"}, False),
            ("Bash", {"command": "cat <<'EOF'\n,task card show\nEOF\n"}, False),
            ("Bash", {"command": "cat /tmp/évidence.txt /home/u/lib/,task/main.py"}, False),
            ("Bash", {"command": ",task card show"}, False),
            ("Bash", {"command": "'/home/u/bin/,task' claim add proof --unknown missing"}, False),
            ("Bash", {"command": "timeout 10 ,task card show"}, False),
            ("Bash", {"command": "env -u AGENT_TASK_SESSION ,task card show"}, False),
            ("Bash", {"command": "pwd && ,task card show"}, False),
            ("Bash", {"command": "pwd\n,task card show"}, False),
            ("Bash", {"command": "bash -c ',task card show'"}, False),
            ("Bash", {"command": "zsh -lc 'cat /home/u/lib/,task/main.py'"}, False),
            ("Bash", {"command": "bash --norc -c ',task card show'"}, False),
            ("Bash", {"command": "bash -c '\"$0\" card show' ,task"}, False),
            ("Bash", {"command": "env --split-string=',task card show' cat"}, False),
            ("Bash", {"command": "rg -- '--pre=,task' file"}, False),
            ("Bash", {"command": "if true; then ,task card show; fi"}, False),
            ("Bash", {"command": 'cat "$(,task card show)"'}, False),
            ("Bash", {"command": "python3 /home/u/lib/,task/main.py card show"}, False),
            ("Bash", {"command": "env -S ',task card show'"}, False),
            ("Bash", {"command": "eval ',task card show'"}, False),
            ("Bash", {"command": "cat ',task"}, False),
            ("Bash", {"command": "printf ',task\\n' | xargs"}, False),
            ("Bash", {"command": "rg --pre ,task pattern file"}, False),
            ("Bash", {"command": "verify-fixture /home/u/lib/,task/main.py"}, False),
            ("Agent", {"prompt": "verify this source"}, False),
            ("Task", {"prompt": "verify this source"}, False),
        ]
        for index, (tool, tool_input, accepted) in enumerate(cases):
            with self.subTest(tool=tool, tool_input=tool_input):
                output = f"source result {index}"
                self.tool_output(output, tool=tool, tool_input=tool_input)
                actual = self.run_task("claim", "add", output, "--quote", output)
                self.assertEqual(actual.returncode == 0, accepted, actual.stderr)

    def test_SHOULD_reject_unadmitted_tools_even_for_stored_claims(self):
        self.set_card()
        cases = [
            ("Agent", {"prompt": "review"}),
            ("Task", {"prompt": "review"}),
            ("Skill", {"skill": "review"}),
            ("GetTask", {"taskId": "background-job"}),
            ("WebSearch", {"query": "fixture"}),
            ("WebFetch", {"url": "https://example.invalid", "prompt": "summarize"}),
            ("mcp__fixture__report", {"query": "fixture"}),
        ]
        for tool, tool_input in cases:
            output = f"unsupported {tool} proof"
            self.tool_output(output, tool=tool, tool_input=tool_input)
            with self.subTest(tool=tool, stage="registration"):
                self.assertNotEqual(self.run_task("claim", "add", output, "--quote", output).returncode, 0)
            # A quote persisted before the exclusion must fail revalidation too.
            transcript = Path(self.env["CLAUDE_CONFIG_DIR"]) / "projects" / "fixture" / "s1.jsonl"
            source = json.loads(transcript.read_text().splitlines()[-1])["uuid"]
            path = next(self.store.rglob("cards.json"))
            cards = json.loads(path.read_text())
            cards["s1"]["claims"] = [
                {
                    "id": "C1",
                    "text": output,
                    "created": datetime.now(timezone.utc).timestamp(),
                    "source": {"kind": "quote", "text": output, "id": source},
                }
            ]
            path.write_text(json.dumps(cards))
            with self.subTest(tool=tool, stage="stored citation"):
                result = self.hook("evidence", answer="Checked:\n- supported [C1]")
                self.assertFalse(result["card"]["claims"][0]["verified"])
                self.assertTrue(result["problems"])

    def test_SHOULD_reject_stale_deleted_and_retargeted_file_claims(self):
        self.set_card()
        target = self.repo / "évidence.txt"
        target.write_text("proof\n")
        (self.repo / "alias").symlink_to(target)
        actual = self.run_task("claim", "add", "proof exists", "--file", "alias:1", "--text", "proof")
        self.assertEqual(actual.returncode, 0, actual.stderr)
        target.unlink()
        self.assertNotEqual(self.run_task("check", "D1", "--claim", "C1").returncode, 0)
        target.write_text("proof\nother content\n")
        self.assertNotEqual(self.run_task("check", "D1", "--claim", "C1").returncode, 0)
        refreshed = self.run_task("claim", "add", "proof exists", "--file", "alias:1", "--text", "proof")
        self.assertEqual(refreshed.returncode, 0, refreshed.stderr)
        self.assertEqual(self.run_task("check", "D1", "--claim", "C2").returncode, 0)

    def test_SHOULD_refuse_empty_sources_and_unknown_claims_as_completion(self):
        self.set_card()
        empty = self.run_task("claim", "add", "x", "--quote", "")
        self.assertNotEqual(empty.returncode, 0)
        actual = self.run_task("claim", "add", "test passed", "--unknown", "test did not run")
        self.assertEqual(actual.returncode, 0, actual.stderr)
        self.assertNotEqual(self.run_task("check", "D1", "--claim", "C1").returncode, 0)
        self.assertIn("D1", self.run_task("status").stdout)

    def test_SHOULD_refuse_relabelled_old_evidence_for_a_stance_reversal(self):
        self.set_card()
        self.tool_output("old result", "2020-01-01T00:00:00+00:00")
        self.run_task("claim", "add", "original reason", "--quote", "old result")
        first = self.run_task("stance", "set", "proposal", "keep it", "--because", "C1")
        self.assertEqual(first.returncode, 0, first.stderr)
        self.run_task("claim", "add", "new label", "--quote", "old result")
        refused = self.run_task("stance", "set", "proposal", "drop it", "--because", "C2")
        self.assertNotEqual(refused.returncode, 0)
        card = json.loads(self.run_task("card", "show", "--json").stdout)
        self.assertEqual([s["value"] for s in card["stances"]], ["keep it"])

    def test_SHOULD_accept_new_evidence_and_keep_stance_history_on_card_rewrite(self):
        self.set_card()
        first = self.claim()
        self.run_task("stance", "set", "proposal", "keep it", "--because", first)
        self.tool_output("new result")
        self.run_task("claim", "add", "new reason", "--quote", "new result")
        actual = self.run_task("stance", "set", "proposal", "drop it", "--because", "C2")
        self.assertEqual(actual.returncode, 0, actual.stderr)
        self.run_task("card", "set", stdin=CARD.replace("Add the export button", "Add export"))
        card = json.loads(self.run_task("card", "show", "--json").stdout)
        self.assertEqual([s["value"] for s in card["stances"]], ["keep it", "drop it"])

    def test_SHOULD_require_new_human_words_for_a_user_driven_reversal(self):
        self.set_card()
        self.transcript_row("user", "keep it", origin="human")
        self.assertEqual(
            self.run_task("stance", "set", "proposal", "keep", "--user", "keep it").returncode,
            0,
        )
        self.transcript_row("user", "drop it", origin="hook")
        refused = self.run_task("stance", "set", "proposal", "drop", "--user", "drop it")
        self.assertNotEqual(refused.returncode, 0)
        self.transcript_row("user", "drop it", origin="human")
        actual = self.run_task("stance", "set", "proposal", "drop", "--user", "drop it")
        self.assertEqual(actual.returncode, 0, actual.stderr)

    def test_SHOULD_refresh_a_stance_reason_without_changing_its_value(self):
        self.set_card()
        claim = self.claim()
        first = self.run_task("stance", "set", "proposal", "keep", "--because", claim)
        self.assertEqual(first.returncode, 0, first.stderr)
        same = self.run_task("stance", "set", "proposal", "keep", "--because", claim)
        self.assertEqual(json.loads(same.stdout)["id"], "S1")
        self.proof.write_text("readme\nnew evidence\n")
        stale = self.run_task("stance", "set", "proposal", "keep", "--because", claim)
        self.assertNotEqual(stale.returncode, 0)
        refreshed = self.run_task("stance", "set", "proposal", "keep", "--because", self.claim())
        self.assertEqual(refreshed.returncode, 0, refreshed.stderr)
        self.assertEqual(json.loads(refreshed.stdout)["id"], "S2")
        self.assertEqual(self.hook("evidence", answer="Assumptions:\n- keep [S2]")["problems"], [])

    def test_SHOULD_keep_evidence_across_compaction_without_accepting_a_rewound_branch(self):
        self.set_card()
        human = self.transcript_row("user", "keep CSV", origin="human")
        self.tool_output("abandoned result")
        self.transcript_row("user", "continue from here", origin="human", parentUuid=human)
        self.tool_output("verified result")
        claim = self.run_task("claim", "add", "the probe passed", "--quote", "verified result")
        self.assertEqual(claim.returncode, 0, claim.stderr)
        self.assertEqual(self.run_task("stance", "set", "format", "CSV", "--user", "keep CSV").returncode, 0)
        candidate = {"anchor": "answer:probe", "concern": "probe failed"}
        self.hook("evidence", findings=[candidate])
        self.assertEqual(self.run_task("finding", "resolve", "F1", "--rejected", "C1").returncode, 0)
        preserved = self.transcript_row("assistant", "last retained answer")
        # The retained attachment can first appear after the boundary, pointing at
        # the summary; preservedSegment still points into the original ancestry.
        self.transcript_row(
            "system",
            [],
            parentUuid=None,
            subtype="compact_boundary",
            logicalParentUuid="retained",
            compactMetadata={"preservedSegment": {"headUuid": preserved, "tailUuid": "retained"}},
        )
        self.transcript_row("user", "untrusted summary", isCompactSummary=True)
        self.transcript_row("attachment", [], uuid="retained")
        tail = self.transcript_row("assistant", "after first compact")
        self.transcript_row("system", [], parentUuid=None, subtype="compact_boundary", logicalParentUuid=tail)
        self.transcript_row("user", "another summary", isCompactSummary=True)
        result = self.hook(
            "evidence", answer="Checked:\n- probe passed [C1]\nAssumptions:\n- CSV [S1]", findings=[candidate]
        )
        self.assertEqual(result["problems"], [])
        self.assertEqual(result["findings"], [])
        self.assertNotEqual(self.run_task("claim", "add", "wrong branch", "--quote", "abandoned result").returncode, 0)

    def test_SHOULD_keep_every_result_of_a_parallel_tool_batch(self):
        self.set_card()
        # Claude writes one row per call of a batch, chained in issue order, hangs each
        # result off its own call and continues from the result that finished last.
        calls = []
        for name in ("one", "two", "three"):
            content = [{"type": "tool_use", "id": name, "name": "Read", "input": {"file_path": f"{name}.py"}}]
            calls.append(self.transcript_row("assistant", content, message={"id": "batch", "content": content}))
        for index in (0, 2, 1):
            result = [
                {"type": "tool_result", "tool_use_id": ("one", "two", "three")[index], "content": f"result {index}"}
            ]
            self.transcript_row("user", result, parentUuid=calls[index])
        self.transcript_row("assistant", "all files read")
        for index in range(3):
            with self.subTest(index=index):
                actual = self.run_task("claim", "add", f"result {index}", "--quote", f"result {index}")
                self.assertEqual(actual.returncode, 0, actual.stderr)
        answer = "Checked:\n- one [C1]\n- two [C2]\n- three [C3]"
        self.assertEqual(self.hook("evidence", answer=answer)["problems"], [])

    def test_SHOULD_refuse_a_rewound_prompt_that_hangs_off_a_kept_answer(self):
        self.set_card()
        answer = self.transcript_row("assistant", "which format?", message={"id": "m1", "content": "which format?"})
        self.transcript_row("user", "drop CSV", origin="human", parentUuid=answer)
        self.transcript_row("user", "keep CSV", origin="human", parentUuid=answer)
        self.transcript_row("assistant", "keeping CSV", message={"id": "m2", "content": "keeping CSV"})
        self.assertNotEqual(self.run_task("stance", "set", "format", "drop", "--user", "drop CSV").returncode, 0)
        kept = self.run_task("stance", "set", "format", "keep", "--user", "keep CSV")
        self.assertEqual(kept.returncode, 0, kept.stderr)

    def test_SHOULD_take_user_words_only_from_prompts_an_adapter_marked_as_typed(self):
        self.set_card()
        self.hook("prompt", text="drop it")
        self.assertNotEqual(self.run_task("stance", "set", "proposal", "drop", "--user", "drop it").returncode, 0)
        self.hook("prompt", text="keep it", origin="human")
        kept = self.run_task("stance", "set", "proposal", "keep", "--user", "keep it")
        self.assertEqual(kept.returncode, 0, kept.stderr)
        # Pi and OMP send typed text from their `input` event.
        self.hook("user", text="drop it")
        dropped = self.run_task("stance", "set", "proposal", "drop", "--user", "drop it")
        self.assertEqual(dropped.returncode, 0, dropped.stderr)

    def test_SHOULD_check_citations_under_each_accepted_report_heading(self):
        self.set_card()
        self.claim()
        for heading in (
            "Checked:",
            "**Checked:**",
            "**Checked**",
            "**Checked** (3 items):",
            "__Checked__ (source)",
            "## Checked (source):",
            "+ Checked:",
        ):
            with self.subTest(heading=heading):
                self.assertEqual(self.hook("evidence", answer=f"{heading}\n- supported [C1]")["problems"], [])
                self.assertTrue(self.hook("evidence", answer=f"{heading}\n- missing citation")["problems"])
                self.assertTrue(self.hook("evidence", answer=f"{heading}\n- nonexistent [C99]")["problems"])

    def test_SHOULD_check_stance_citations_under_plus_prefixed_headings(self):
        self.set_card()
        for section in ("Assumptions", "Proposed", "Decision needed"):
            with self.subTest(section=section):
                self.assertTrue(self.hook("evidence", answer=f"+ {section}:\n  - missing citation")["problems"])
                self.assertIn(
                    "unknown S99", self.hook("evidence", answer=f"+ {section}:\n  - decision [S99]")["problems"]
                )

    def test_SHOULD_require_a_report_item_beyond_quoted_or_fenced_examples(self):
        self.set_card()
        for body in ("", "> - tests passed", "```\n- tests passed\n```", "~~~\n- tests passed"):
            with self.subTest(body=body):
                self.assertTrue(self.hook("evidence", answer=f"Checked:\n{body}")["problems"])
        self.assertTrue(self.hook("evidence", answer="Checked:\n\nAssumptions: none")["problems"])
        self.assertEqual(self.hook("evidence", answer="Checked: none")["problems"], [])
        self.assertEqual(self.hook("evidence", answer="> Checked:\n> - quoted example [C99]")["problems"], [])

    def test_SHOULD_verify_user_quote_line_endings_as_they_were_accepted(self):
        self.set_card()
        self.transcript_row("user", "keep\nCSV", origin="human")
        stance = self.run_task("stance", "set", "format", "CSV", "--user", "keep\r\nCSV")
        self.assertEqual(stance.returncode, 0, stance.stderr)
        self.assertEqual(self.hook("evidence", answer="Assumptions:\n- keep CSV [S1]")["problems"], [])

    def test_SHOULD_ignore_only_properly_delimited_code_examples(self):
        self.set_card()
        for opening, inner, closing in (
            ("````markdown", "```", "````"),
            ("~~~", "~~~ language", "~~~~"),
            ("```", "    ```", "```"),
            ("```", "~~~", "```"),
        ):
            example = f"{opening}\n{inner}\nChecked: example [C99]\n{closing}"
            with self.subTest(example=example):
                self.assertEqual(self.hook("evidence", answer=example)["problems"], [])
                self.assertTrue(self.hook("evidence", answer=example + "\nChecked: real claim [C99]")["problems"])

    def test_SHOULD_remember_resolutions_without_hiding_a_different_finding_on_the_same_line(
        self,
    ):
        self.set_card()
        candidate = {"anchor": "README.md:1", "concern": "missing heading"}
        self.hook("evidence", findings=[candidate])
        claim = self.claim()
        self.assertEqual(self.run_task("finding", "resolve", "F1", "--rejected", claim).returncode, 0)
        actual = self.hook(
            "evidence",
            findings=[candidate, {"anchor": "README.md:1", "concern": "wrong link"}],
        )
        self.assertEqual([f["concern"] for f in actual["findings"]], ["wrong link"])
        self.assertEqual(actual["card"]["findings"][0]["status"], "rejected")

    def test_SHOULD_reopen_a_resolved_finding_only_with_newer_tool_evidence(self):
        self.set_card()
        candidate = {"anchor": "answer:tests passed", "concern": "test failed"}
        self.hook("evidence", findings=[candidate])
        self.run_task("finding", "resolve", "F1", "--fixed", self.claim())
        self.tool_output("regression found")
        actual = self.hook("evidence", findings=[{**candidate, "quote": "regression found"}])
        self.assertEqual([f["id"] for f in actual["findings"]], ["F2"])

    def test_SHOULD_require_valid_citations_per_report_item_and_recheck_completion(
        self,
    ):
        self.set_card()
        self.mark("D1")
        answer = "Checked:\n- source matches [C1]\n- another claim\nAssumptions:\n- a decision [S99]"
        actual = self.hook("evidence", answer=answer)
        self.assertEqual(len(actual["problems"]), 2)
        self.proof.write_text("changed\n")
        stale = self.hook("evidence", answer="Checked:\n- source matches [C1]")
        self.assertTrue(any("D1" in p for p in stale["problems"]))

    def test_SHOULD_number_done_items_and_refuse_a_card_without_scope(self):
        saved = self.set_card()
        self.assertEqual(saved.returncode, 0, saved.stderr)
        self.assertIn("- [ ] D1: the button downloads a CSV", saved.stdout)
        self.assertIn("- [ ] D2: tests cover the export", saved.stdout)

        refused = self.run_task("card", "set", stdin="Goal: x\nDone when: y\n")
        self.assertEqual(refused.returncode, 2)
        self.assertIn("Scope:", refused.stderr)

    def test_SHOULD_refuse_the_first_uncarded_edit_once_and_allow_scratch(self):
        self.hook("prompt", text="fix it")
        self.assertEqual(self.hook("tool", tool="Write", paths=["/tmp/notes.txt"]), {})
        first = self.hook("tool", tool="Edit", paths=["src/app.py"])
        self.assertIn("no intent card", first["deny"])
        self.assertEqual(self.hook("tool", tool="Edit", paths=["src/app.py"]), {})

    def test_SHOULD_flag_edits_and_dirty_files_outside_scope_until_recorded(self):
        self.set_card()
        self.assertEqual(self.hook("tool", tool="Edit", paths=["src/app.py"]), {})
        note = self.hook("tool", tool="Edit", paths=["docs/x.md"])["note"]
        self.assertIn("docs/x.md is outside the card's `Scope:`", note)

        (self.repo / "docs").mkdir()
        (self.repo / "docs" / "x.md").write_text("x\n")
        for item in ("D1", "D2"):
            self.mark(item)
        block = self.hook("stop", answer="done")["block"]
        self.assertIn("docs/x.md", block)

        self.run_task("scope", "add", "docs/x.md", "--reason", "the button needs a doc link")
        self.assertEqual(self.hook("stop", answer="done"), {})

    def test_SHOULD_ignore_files_already_dirty_when_the_card_was_set(self):
        (self.repo / "README.md").write_text("changed before the task\n")
        self.set_card()
        self.hook("tool", tool="Edit", paths=["src/app.py"])
        for item in ("D1", "D2"):
            self.mark(item)
        self.assertEqual(self.hook("stop", answer="done"), {})

    def test_SHOULD_hold_a_turn_to_its_card_when_a_shell_command_did_the_writing(self):
        (self.repo / "src").mkdir()
        (self.repo / "src" / "app.py").write_text("v1\n")
        (self.repo / "notes.txt").write_text("the user's scratch\n")
        self.set_card()
        self.hook("prompt", text="go on")
        # Before the command: the user's own untracked file changes; it is not the command's.
        (self.repo / "notes.txt").write_text("the user's scratch, edited\n")
        self.hook("tool", tool="Bash", phase="before", call_id="shell")
        (self.repo / "src" / "app.py").write_text("v2, written by a shell command\n")
        (self.repo / "docs").mkdir()
        (self.repo / "docs" / "x.md").write_text("x\n")
        note = self.hook("tool", tool="Bash", phase="after", call_id="shell")["note"]
        self.assertIn("docs/x.md is outside the card's `Scope:`", note)
        self.assertNotIn("notes.txt", note)
        block = self.hook("stop", answer="done")["block"]
        self.assertIn("D1: the button downloads a CSV", block)
        self.assertIn("docs/x.md", block)
        self.assertNotIn("notes.txt", block)

    def test_SHOULD_refuse_to_mark_another_sessions_card(self):
        self.set_card()
        self.assertEqual(self.mark("D1", session="s1").returncode, 0)
        other = self.run_task("check", "D2", "--claim", "C1", "--session", "s2")
        self.assertIn("no card for session s2", other.stderr)
        self.assertIn("D2", self.run_task("status", "--session", "s1").stdout)

    def test_SHOULD_drop_item_ids_the_agent_wrote_into_the_card(self):
        saved = self.set_card(CARD.replace("- the button downloads a CSV", "- D1 the button downloads a CSV"))
        self.assertIn("- [ ] D1: the button downloads a CSV", saved.stdout)

    def test_SHOULD_send_the_stop_back_while_items_are_open_and_give_up_on_a_repeat(
        self,
    ):
        self.set_card()
        self.hook("tool", tool="Edit", paths=["src/app.py"])
        block = self.hook("stop", answer="all done")["block"]
        self.assertIn("D1: the button downloads a CSV", block)
        self.assertEqual(self.hook("stop", answer="all done"), {})

        self.hook("prompt", text="continue")
        self.hook("tool", tool="Edit", paths=["src/app.py"])
        self.mark("D1", "clicked it")
        self.assertIn("D2", self.hook("stop", answer="x")["block"])
        self.run_task("block", "D2", "--reason", "no test runner here")
        self.assertEqual(self.hook("stop", answer="x"), {})

    def test_SHOULD_stop_sending_back_after_three_continues(self):
        self.set_card()
        self.hook("prompt", text="go")
        results = []
        for i in range(5):
            self.hook("tool", tool="Write", paths=[f"stray{i}.txt"])
            (self.repo / f"stray{i}.txt").write_text("x\n")
            results.append("block" in self.hook("stop", answer="x"))
        self.assertEqual(results, [True, True, True, False, False])

    def test_SHOULD_keep_item_status_when_the_card_is_rewritten(self):
        self.set_card()
        self.mark("D1", "clicked it")
        rewritten = self.run_task("card", "set", stdin=CARD.replace("on the report page", "on the summary page"))
        self.assertIn("- [x] D1: the button downloads a CSV — [C1] clicked it", rewritten.stdout)

    def test_SHOULD_reopen_items_when_the_goal_changes(self):
        self.set_card()
        self.mark("D1", "clicked it")
        # Evidence for one goal does not prove another.
        moved = self.run_task("card", "set", stdin=CARD.replace("Add the export button", "Add CSV and XLSX export"))
        self.assertIn("- [ ] D1: the button downloads a CSV", moved.stdout)
        self.assertIn("Earlier goal: Add the export button", moved.stdout)

    def add_scope_changes(self, count: int) -> None:
        for i in range(count):
            self.run_task(
                "scope", "add", f"docs/page{i}.md", "--reason", "the export needs a documented link on this page"
            )

    def test_SHOULD_show_the_latest_five_scope_changes_and_keep_all_for_show_and_scope_checks(self):
        self.set_card()
        self.add_scope_changes(30)
        rewritten = self.run_task("card", "set", stdin=CARD)
        self.assertIn("Scope changes: 25 older ones", rewritten.stdout)
        self.assertEqual(rewritten.stdout.count("Scope change: "), 5)
        self.assertEqual(self.hook("tool", tool="Edit", paths=["docs/page0.md"]), {})
        self.assertEqual(self.run_task("card", "show").stdout.count("Scope change: "), 30)

    def test_SHOULD_measure_the_size_limit_on_the_agent_text_and_say_the_card_saved(
        self,
    ):
        self.set_card()
        self.add_scope_changes(30)
        for item in ("D1", "D2"):
            self.mark(item, "ran the export and opened the file " * 40)
        rewritten = self.run_task("card", "set", stdin=CARD)
        self.assertEqual(rewritten.returncode, 0, rewritten.stderr)
        self.assertNotIn("bytes", rewritten.stderr)

        long = CARD.replace(
            "Reading: The user wants CSV export on the report page.", "Reading: " + "the report page needs it " * 100
        )
        warned = self.run_task("card", "set", stdin=long)
        self.assertEqual(warned.returncode, 0)
        self.assertIn("card saved", warned.stderr)
        self.assertIn("Goal: Add the export button", self.run_task("card", "show").stdout)

    def test_SHOULD_archive_scope_changes_and_keep_one_earlier_goal_when_the_goal_changes(self):
        self.set_card()
        self.run_task("scope", "add", "docs/x.md", "--reason", "the button needs a doc link")
        moved = self.run_task("card", "set", stdin=CARD.replace("Add the export button", "Add CSV export"))
        self.assertIn("archived these scope changes: docs/x.md", moved.stderr)
        shown = self.run_task("card", "set", stdin=CARD.replace("Add the export button", "Add XLSX export")).stdout
        self.assertNotIn("Scope change: docs/x.md", shown)
        self.assertNotIn("Earlier goal: Add the export button", shown)
        self.assertIn("Earlier goal: Add CSV export", shown)
        # An archived scope change is a record only: the new goal records its own.
        self.assertIn("docs/x.md is outside", self.hook("tool", tool="Edit", paths=["docs/x.md"])["note"])

    def test_SHOULD_hide_another_sessions_card(self):
        self.set_card()
        self.assertIn("Goal: Add the export button", self.hook("prompt", text="go")["context"])
        self.assertNotIn("Intent card", self.hook("prompt", session="s2", text="unrelated").get("context", ""))
        self.assertIn("deny", self.hook("tool", session="s2", tool="Edit", paths=["src/app.py"]))

    def test_SHOULD_record_a_correction_and_suggest_saving_a_lasting_preference(self):
        self.set_card()
        context = self.hook("prompt", text="no, I didn't ask for PDF. In general we never add formats unasked")[
            "context"
        ]
        self.assertIn("This message corrects you", context)
        self.assertIn("the evidence says otherwise, say so in one line", context)
        self.assertIn(",task pref add", context)
        card = json.loads(self.run_task("card", "show", "--json").stdout)
        self.assertEqual(card["corrections"], ["no, I didn't ask for PDF. In general we never add formats unasked"])
        log = (self.store / "steering.jsonl").read_text().splitlines()
        self.assertEqual(json.loads(log[0])["harness"], "test")

        self.assertNotIn("corrects you", self.hook("prompt", text="add tests for the button")["context"])

    def test_SHOULD_load_preferences_on_the_first_prompt_of_a_session(self):
        self.run_task("pref", "add", "never open PRs in this repo")
        self.run_task("pref", "add", "answer briefly", "--global")
        first = self.hook("prompt", text="hi")["context"]
        self.assertIn("- never open PRs in this repo", first)
        self.assertIn("- answer briefly", first)
        self.assertEqual(self.hook("prompt", text="next"), {})

    def test_SHOULD_ask_for_a_zoom_out_every_25_steps_and_after_compaction(self):
        self.set_card()
        notes = [self.hook("tool", tool="Bash").get("note", "") for _ in range(25)]
        self.assertEqual([i for i, note in enumerate(notes) if "zoom out" in note], [24])

        instructions = self.hook("compact")["instructions"]
        self.assertIn("Goal: Add the export button", instructions)
        note = self.hook("tool", tool="Bash")["note"]
        self.assertIn("zoom out", note)
        self.assertIn("the Goal or the ask itself is off", note)

    def test_SHOULD_speak_codex_hook_json(self):
        self.set_card()
        base = {"session_id": "s1", "cwd": str(self.repo)}
        prompt = self.hook("codex", **base, hook_event_name="UserPromptSubmit", prompt="go")
        self.assertIn("Goal:", prompt["hookSpecificOutput"]["additionalContext"])
        # Codex runs UserPromptSubmit only for the user's own input, so the prompt is the user's words.
        self.assertEqual(self.run_task("stance", "set", "start", "now", "--user", "go").returncode, 0)

        patch = "*** Begin Patch\n*** Update File: lib/other.py\n@@\n"
        post = self.hook(
            "codex", **base, hook_event_name="PostToolUse", tool_name="apply_patch", tool_input={"command": patch}
        )
        self.assertIn("lib/other.py is outside", post["hookSpecificOutput"]["additionalContext"])

        compacted = self.hook("codex", **base, hook_event_name="SessionStart", source="compact")
        self.assertIn(
            "The conversation was compacted. Intent card", compacted["hookSpecificOutput"]["additionalContext"]
        )

        stop = self.hook("codex", **base, hook_event_name="Stop", last_assistant_message="done")
        self.assertEqual(stop["decision"], "block")
        self.assertIn("D1", stop["reason"])

        fresh = self.hook(
            "codex",
            session_id="s2",
            cwd=str(self.repo),
            hook_event_name="PreToolUse",
            tool_name="apply_patch",
            tool_input={"command": patch},
        )
        self.assertEqual(fresh["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_SHOULD_exit_nonzero_from_status_while_items_are_open(self):
        self.set_card()
        self.assertEqual(self.run_task("status").returncode, 1)
        self.mark("d1", "ok")
        self.run_task("block", "D2", "--reason", "later")
        self.assertEqual(self.run_task("status").returncode, 0)
        self.assertEqual(self.run_task("check", "D9", "--claim", "C1").returncode, 1)

    def test_SHOULD_not_hold_a_turn_that_wrote_nothing_to_the_card(self):
        self.set_card()
        self.hook("prompt", text="what does the README say?")
        self.hook("tool", tool="Read", paths=["README.md"])
        self.assertEqual(self.hook("stop", answer="It says readme."), {})

    def test_SHOULD_leave_files_the_user_changed_before_the_turn_alone(self):
        self.set_card()
        (self.repo / "notes.txt").write_text("the user's own edit\n")
        self.hook("prompt", text="go on")
        self.hook("tool", tool="Edit", paths=["src/app.py"])
        self.hook("tool", tool="Bash", phase="before", call_id="stray")
        (self.repo / "stray.txt").write_text("written by a Bash command\n")
        self.hook("tool", tool="Bash", phase="after", call_id="stray")
        for item in ("D1", "D2"):
            self.mark(item)
        block = self.hook("stop", answer="done")["block"]
        self.assertIn("stray.txt", block)
        self.assertNotIn("notes.txt", block)

    def test_SHOULD_strip_bold_headings_and_never_widen_scope_from_them(self):
        self.hook("prompt", text="go")
        saved = self.run_task("card", "set", stdin="**Goal:** export\n**Done when:**\n- it works\n**Scope:** src/\n")
        self.assertIn("Goal: export\nDone when:\n- [ ] D1: it works\nScope: src/", saved.stdout)
        self.assertEqual(self.run_task("scope", "check", "README.md").returncode, 1)

    def test_SHOULD_match_scope_through_symlinks_and_root_level_globs(self):
        self.hook("prompt", text="go")
        self.run_task("card", "set", stdin="Goal: g\nDone when: d\nScope: src/; **/*.py\n")
        link = Path(self.tmp.name) / "link"
        link.symlink_to(self.repo)
        (self.repo / "src").mkdir()
        self.assertEqual(self.run_task("scope", "check", "src/x.ts", cwd=link).returncode, 0)
        self.assertEqual(self.run_task("scope", "check", "a.py", "lib/b.py").returncode, 0)
        self.assertEqual(self.run_task("scope", "check", "a.ts").returncode, 1)

    def test_SHOULD_refuse_to_guess_the_session_when_two_are_active(self):
        self.hook("prompt", session="a", text="task a")
        self.hook("prompt", session="b", text="question b")
        refused = self.run_task("card", "set", stdin=CARD)
        self.assertEqual(refused.returncode, 2)
        self.assertIn("--session", refused.stderr)
        deny = self.hook("tool", session="a", tool="Edit", paths=["src/a.py"])["deny"]
        self.assertIn(",task card set --session a", deny)
        self.assertEqual(self.run_task("card", "set", "--session", "a", stdin=CARD).returncode, 0)
        self.assertNotIn("Intent card", self.hook("prompt", session="b", text="another question").get("context", ""))
        self.assertIn("deny", self.hook("tool", session="b", tool="Edit", paths=["src/b.py"]))
        self.assertEqual(self.hook("tool", session="a", tool="Edit", paths=["src/a.py"]), {})

    def test_SHOULD_let_the_next_session_claim_a_card_set_by_hand(self):
        self.run_task("card", "set", stdin=CARD)
        self.assertIn("Goal: Add the export button", self.hook("prompt", session="s7", text="go")["context"])
        self.assertNotIn("Intent card", self.hook("prompt", session="s8", text="go").get("context", ""))

    def test_SHOULD_not_take_an_aside_for_a_correction(self):
        self.set_card()
        for text in ("No rush, also add a docs page", "don't forget the tests", "use pandas instead of csv"):
            self.assertNotIn("corrects you", self.hook("prompt", text=text)["context"], text)

    def test_SHOULD_keep_plain_double_star_and_dunder_scope_entries(self):
        self.hook("prompt", text="go")
        self.run_task("card", "set", stdin="Goal: g\nDone when: d\nScope: **/tests/**, __init__.py\n")
        card = json.loads(self.run_task("card", "show", "--json").stdout)
        self.assertEqual(card["scope"], ["**/tests/**", "__init__.py"])
        self.assertEqual(self.run_task("scope", "check", "tests/u.py", "src/tests/t.py", "__init__.py").returncode, 0)

    def test_SHOULD_not_push_open_items_on_a_turn_whose_tools_wrote_nothing(self):
        self.set_card()
        self.hook("prompt", text="why does the test fail?")
        (self.repo / "README.md").write_text("the user edits meanwhile\n")
        result = self.hook("stop", answer="Because X.")
        self.assertNotIn("D1", result.get("block", ""))

    def test_SHOULD_name_the_session_id_when_another_session_shares_the_worktree(self):
        self.hook("prompt", session="old", text="earlier task")
        context = self.hook("prompt", session="new", text="add the button")["context"]
        self.assertIn(",task card set --session new", context)

    def test_SHOULD_leave_a_card_set_by_hand_long_after_the_last_session_unowned(self):
        self.hook("prompt", session="old", text="earlier task")
        state_path = next(self.store.glob("*/state.json"))
        state = json.loads(state_path.read_text())
        state["sessions"]["old"] -= 7 * 3600
        state_path.write_text(json.dumps(state))
        self.run_task("card", "set", stdin=CARD)
        self.assertIn("Goal: Add the export button", self.hook("prompt", session="fresh", text="go")["context"])

    def test_SHOULD_keep_two_sessions_cards_and_clear_only_the_selected_one(self):
        self.hook("prompt", session="a", text="task a")
        self.run_task("card", "set", "--session", "a", stdin=CARD)
        self.hook("prompt", session="b", text="task b")
        self.run_task("card", "set", "--session", "b", stdin=CARD.replace("export button", "PDF button"))
        self.assertIn("export button", self.run_task("card", "show", "--session", "a").stdout)
        self.run_task("card", "clear", "--session", "b")
        self.assertIn("export button", self.run_task("card", "show", "--session", "a").stdout)
        self.assertNotEqual(self.run_task("card", "show", "--session", "b").returncode, 0)
        self.run_task("card", "set", "--session", "b", stdin=CARD)
        self.assertIn("D1", self.run_task("status", "--session", "b").stdout)

    def test_SHOULD_resolve_environment_session_for_item_updates(self):
        self.set_card()
        self.env["AGENT_TASK_SESSION"] = "other"
        result = self.run_task("check", "D1", "--claim", "C1")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("D1", self.run_task("status", "--session", "s1").stdout)

    def test_SHOULD_refuse_ambiguous_mutations_without_a_session(self):
        self.set_card()
        self.hook("prompt", session="s2", text="other task")
        result = self.run_task("check", "D1", "--claim", "C1")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--session", result.stderr)

    def test_SHOULD_keep_all_parallel_hook_updates(self):
        self.set_card()
        with ThreadPoolExecutor(max_workers=12) as pool:
            list(pool.map(lambda _: self.hook("tool", tool="Read"), range(12)))
        state = json.loads(next(self.store.glob("*/state.json")).read_text())
        self.assertEqual(state["turns"]["s1"]["steps"], 12)

    def test_SHOULD_ignore_user_edits_between_prompt_and_read(self):
        self.set_card()
        self.hook("prompt", text="what does the README say?")
        (self.repo / "README.md").write_text("user changed it")
        self.assertEqual(self.hook("tool", tool="Read", paths=["README.md"]), {})
        self.assertEqual(self.hook("stop", answer="read it"), {})

    def test_SHOULD_track_shell_edits_to_an_existing_untracked_file(self):
        self.set_card()
        (self.repo / "new.py").write_text("previous turn")
        self.hook("prompt", text="continue")
        self.hook("tool", tool="Bash", phase="before", call_id="shell-1")
        (self.repo / "new.py").write_text("updated by this command")
        result = self.hook("tool", tool="Bash", phase="after", call_id="shell-1")
        self.assertIn("new.py", result.get("note", ""))
        self.assertIn("D1", self.hook("stop", answer="done").get("block", ""))

    def test_SHOULD_only_block_actual_changes_through_a_staging_and_restore_cycle(self):
        target = self.repo / "éxport.txt"
        target.write_text("original\n")
        self.set_card()
        self.mark("D1")
        self.mark("D2")

        self.hook("tool", tool="Bash", phase="before", call_id="stage")
        subprocess.run(["git", "add", "éxport.txt"], cwd=self.repo, env=self.env, check=True)
        self.assertEqual(self.hook("tool", tool="Bash", phase="after", call_id="stage"), {})
        self.assertEqual(self.hook("stop", answer="done"), {})

        self.hook("tool", tool="Bash", phase="before", call_id="unstage")
        subprocess.run(["git", "reset", "-q", "HEAD", "--", "éxport.txt"], cwd=self.repo, env=self.env, check=True)
        self.assertEqual(self.hook("tool", tool="Bash", phase="after", call_id="unstage"), {})

        self.hook("tool", tool="Bash", phase="before", call_id="touch")
        stamp = target.stat()
        os.utime(target, ns=(stamp.st_atime_ns, stamp.st_mtime_ns + 1_000_000_000))
        self.assertEqual(self.hook("tool", tool="Bash", phase="after", call_id="touch"), {})

        self.hook("tool", tool="Bash", phase="before", call_id="edit")
        stamp = target.stat()
        target.write_text("modified\n")
        os.utime(target, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
        actual = self.hook("tool", tool="Bash", phase="after", call_id="edit")
        self.assertIn("éxport.txt", actual.get("note", ""))
        self.assertIn("éxport.txt", self.hook("stop", answer="done").get("block", ""))

        self.hook("tool", tool="Bash", phase="before", call_id="restore")
        target.write_text("original\n")
        self.hook("tool", tool="Bash", phase="after", call_id="restore")
        self.assertEqual(self.run_task("card", "set", stdin=CARD).returncode, 0)
        self.assertEqual(self.hook("stop", answer="done"), {})

    def test_SHOULD_clear_a_direct_edit_restored_to_preexisting_dirty_content_at_stop(self):
        target = self.repo / "README.md"
        target.write_text("the user's preexisting change\n")
        self.set_card()
        self.mark("D1")
        self.mark("D2")
        self.hook("tool", tool="Edit", paths=["README.md"], phase="before", call_id="edit")
        target.write_text("the agent's change\n")
        actual = self.hook("tool", tool="Edit", paths=["README.md"], phase="after", call_id="edit")
        self.assertIn("README.md", actual.get("note", ""))

        target.write_text("the user's preexisting change\n")

        self.assertEqual(self.hook("stop", answer="restored"), {})

    def test_SHOULD_block_deletion_until_an_untracked_file_is_restored(self):
        target = self.repo / "notes.txt"
        target.write_text("preexisting\n")
        self.set_card()
        self.mark("D1")
        self.mark("D2")
        self.hook("tool", tool="Bash", phase="before", call_id="delete")
        target.unlink()
        self.hook("tool", tool="Bash", phase="after", call_id="delete")
        self.assertIn("notes.txt", self.hook("stop", answer="done").get("block", ""))

        self.hook("tool", tool="Write", paths=["notes.txt"], phase="before", call_id="readd")
        target.write_text("preexisting\n")
        self.hook("tool", tool="Write", paths=["notes.txt"], phase="after", call_id="readd")

        self.assertEqual(self.run_task("card", "set", stdin=CARD).returncode, 0)
        self.assertEqual(self.hook("stop", answer="restored"), {})

    def test_SHOULD_block_a_clean_tracked_deletion_until_restored(self):
        target = self.repo / "README.md"
        self.set_card()
        self.mark("D1")
        self.mark("D2")
        self.hook("tool", tool="Bash", phase="before", call_id="delete")

        target.unlink()

        actual = self.hook("tool", tool="Bash", phase="after", call_id="delete")
        self.assertIn("README.md", actual.get("note", ""))
        self.assertIn("README.md", self.hook("stop", answer="done").get("block", ""))

        self.hook("tool", tool="Write", paths=["README.md"], phase="before", call_id="restore")
        target.write_text("readme\n")
        self.hook("tool", tool="Write", paths=["README.md"], phase="after", call_id="restore")
        self.assertEqual(self.run_task("card", "set", stdin=CARD).returncode, 0)
        self.assertEqual(self.hook("stop", answer="restored"), {})

    def test_SHOULD_ignore_a_commit_that_leaves_existing_file_contents_unchanged(self):
        target = self.repo / "notes.txt"
        target.write_text("preexisting\n")
        self.set_card()
        self.hook("tool", tool="Bash", phase="before", call_id="commit")
        subprocess.run(["git", "add", "notes.txt"], cwd=self.repo, env=self.env, check=True)
        subprocess.run(
            ["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "fixture"],
            cwd=self.repo,
            env=self.env,
            check=True,
        )

        self.assertEqual(self.hook("tool", tool="Bash", phase="after", call_id="commit"), {})
        self.assertEqual(self.hook("stop", answer="no file edit"), {})

    def test_SHOULD_detect_permission_changes_without_a_timestamp_change(self):
        target = self.repo / "notes.txt"
        target.write_text("preexisting\n")
        target.chmod(0o644)
        self.set_card()
        self.mark("D1")
        self.mark("D2")
        self.hook("tool", tool="Bash", phase="before", call_id="chmod")

        target.chmod(0o600)

        actual = self.hook("tool", tool="Bash", phase="after", call_id="chmod")
        self.assertIn("notes.txt", actual.get("note", ""))
        self.assertIn("notes.txt", self.hook("stop", answer="done").get("block", ""))

    def test_SHOULD_attribute_a_change_that_makes_a_dirty_file_unreadable(self):
        target = self.repo / "notes.txt"
        target.write_text("preexisting\n")
        self.set_card()
        self.mark("D1")
        self.mark("D2")
        self.hook("tool", tool="Bash", phase="before", call_id="chmod")

        target.chmod(0)

        actual = self.hook("tool", tool="Bash", phase="after", call_id="chmod")
        self.assertIn("notes.txt", actual.get("note", ""))
        self.assertIn("notes.txt", self.hook("stop", answer="done").get("block", ""))

    def test_SHOULD_keep_tracking_other_writes_with_an_unreadable_dirty_file(self):
        target = self.repo / "unreadable.txt"
        target.write_text("preexisting\n")
        target.chmod(0)
        self.set_card()
        self.hook("tool", tool="Bash", phase="before", call_id="write")

        (self.repo / "notes.txt").write_text("new\n")

        actual = self.hook("tool", tool="Bash", phase="after", call_id="write")
        self.assertIn("notes.txt", actual.get("note", ""))
        self.assertNotIn("unreadable.txt", actual.get("note", ""))

    def test_SHOULD_track_symlink_retargeting_instead_of_following_its_target(self):
        other = Path(self.tmp.name) / "other.txt"
        other.write_bytes(self.proof.read_bytes())
        stamp = self.proof.stat()
        os.utime(other, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
        link = self.repo / "alias"
        link.symlink_to(self.proof)
        self.set_card()
        self.mark("D1")
        self.mark("D2")
        self.hook("tool", tool="Bash", phase="before", call_id="retarget")

        link.unlink()
        link.symlink_to(other)

        actual = self.hook("tool", tool="Bash", phase="after", call_id="retarget")
        self.assertIn("alias", actual.get("note", ""))
        self.assertIn("alias", self.hook("stop", answer="done").get("block", ""))

    def test_SHOULD_detect_replacing_a_symlink_with_a_file_of_the_same_contents(self):
        link = self.repo / "alias"
        link.symlink_to(self.proof)
        stamp = self.proof.stat()
        self.set_card()
        self.hook("tool", tool="Bash", phase="before", call_id="replace")

        link.unlink()
        link.write_bytes(self.proof.read_bytes())
        os.utime(link, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))

        actual = self.hook("tool", tool="Bash", phase="after", call_id="replace")
        self.assertIn("alias", actual.get("note", ""))

    def test_SHOULD_attribute_a_direct_edit_through_a_symlink_to_its_target(self):
        (self.repo / "src").mkdir()
        (self.repo / "src/alias").symlink_to(self.repo / "README.md")
        self.set_card()
        self.mark("D1")
        self.mark("D2")
        self.hook("tool", tool="Edit", paths=["src/alias"], phase="before", call_id="edit")

        (self.repo / "README.md").write_text("edited through src/alias\n")

        actual = self.hook("tool", tool="Edit", paths=["src/alias"], phase="after", call_id="edit")
        self.assertIn("README.md", actual.get("note", ""))
        self.assertIn("README.md", self.hook("stop", answer="done").get("block", ""))

    def test_SHOULD_resolve_symlink_parents_before_dot_dot_in_direct_edits(self):
        (self.repo / "outside/nested").mkdir(parents=True)
        (self.repo / "src").mkdir()
        (self.repo / "src/link").symlink_to("../outside/nested", target_is_directory=True)
        target = self.repo / "outside/target.txt"
        target.write_text("preexisting\n")
        self.set_card()
        self.mark("D1")
        self.mark("D2")
        self.hook("tool", tool="Edit", paths=["src/link/../target.txt"], phase="before", call_id="edit")

        target.write_text("edited\n")

        actual = self.hook("tool", tool="Edit", paths=["src/link/../target.txt"], phase="after", call_id="edit")
        self.assertIn("outside/target.txt", actual.get("note", ""))
        self.assertIn("outside/target.txt", self.hook("stop", answer="done").get("block", ""))

    def test_SHOULD_parse_omp_hashline_targets_and_move_destinations(self):
        self.hook("prompt", text="edit")
        patch = "*** Begin Patch\n[src/a.py#abcd]\nPUT 1.=1:\n+new\nMV docs/new name.py\n*** End Patch"
        refused = self.hook("tool", tool="edit", paths=["src/a.py"], patch=patch, phase="before")
        self.assertIn("deny", refused)
        self.run_task("card", "set", stdin=CARD)
        result = self.hook("tool", tool="edit", paths=["src/a.py"], patch=patch, phase="after")
        self.assertIn("docs/new name.py", result.get("note", ""))

    def test_SHOULD_preserve_spaces_in_scope_entries(self):
        self.set_card(CARD.replace("src/, tests/*.py", "My Project/"))
        self.assertEqual(self.run_task("scope", "check", "My Project/file.py").returncode, 0)
        self.assertEqual(self.run_task("scope", "check", "My/file.py").returncode, 1)

    def test_SHOULD_separate_preferences_for_repositories_with_the_same_name(self):
        other = Path(self.tmp.name) / "other" / "work"
        other.mkdir(parents=True)
        subprocess.run(["git", "init", "-q", str(other)], check=True, env=self.env)
        self.run_task("pref", "add", "only in the first repository")
        self.assertEqual(self.run_task("pref", "list", cwd=other).stdout, "")

    def test_SHOULD_pair_parallel_shell_snapshots_by_call_id(self):
        self.set_card()
        self.hook("tool", tool="Bash", phase="before", call_id="one")
        self.hook("tool", tool="Bash", phase="before", call_id="two")
        (self.repo / "README.md").write_text("command one changed it")
        self.hook("tool", tool="Bash", phase="after", call_id="one")
        (self.repo / "later.py").write_text("command two changed it")
        self.assertIn("later.py", self.hook("tool", tool="Bash", phase="after", call_id="two")["note"])

    def test_SHOULD_restore_the_earliest_overlapping_shell_state_regardless_of_completion_order(self):
        for restored, should_block in (("A", False), ("B", True)):
            with self.subTest(restored=restored):
                target = self.repo / "notes.txt"
                target.write_text("A")
                self.set_card()
                self.mark("D1")
                self.mark("D2")
                self.hook("tool", tool="Bash", phase="before", call_id="long")
                target.write_text("B")
                self.hook("tool", tool="Bash", phase="before", call_id="short")
                target.write_text("C")
                self.hook("tool", tool="Bash", phase="after", call_id="short")
                self.hook("tool", tool="Bash", phase="after", call_id="long")

                target.write_text(restored)

                actual = self.hook("stop", answer="restored")
                self.assertEqual(bool(actual.get("block")), should_block, actual)

    def test_SHOULD_ignore_an_unfinished_failed_capture_when_later_edits_restore(self):
        target = self.repo / "notes.txt"
        target.write_text("A")
        self.set_card()
        self.mark("D1")
        self.mark("D2")
        self.hook("tool", tool="Edit", paths=["notes.txt"], phase="before", call_id="failed")
        target.write_text("B")
        self.hook("tool", tool="Bash", phase="before", call_id="successful")
        target.write_text("C")
        self.hook("tool", tool="Bash", phase="after", call_id="successful")

        target.write_text("B")

        self.assertEqual(self.hook("stop", answer="restored"), {})

    def test_SHOULD_refine_a_baseline_when_an_earlier_completed_call_already_sees_restored_content(self):
        target = self.repo / "notes.txt"
        target.write_text("A")
        self.set_card()
        self.mark("D1")
        self.mark("D2")
        self.hook("tool", tool="Bash", phase="before", call_id="long")
        target.write_text("B")
        self.hook("tool", tool="Edit", paths=["notes.txt"], phase="before", call_id="short")
        target.write_text("C")
        self.hook("tool", tool="Edit", paths=["notes.txt"], phase="after", call_id="short")

        target.write_text("A")
        self.hook("tool", tool="Bash", phase="after", call_id="long")

        self.assertEqual(self.hook("stop", answer="restored"), {})

    def test_SHOULD_restore_the_earliest_background_state_when_a_direct_edit_completes_first(self):
        for restored, should_block in (("A", False), ("B", True)):
            with self.subTest(restored=restored):
                target = self.repo / "notes.txt"
                target.write_text("A")
                self.set_card()
                self.mark("D1")
                self.mark("D2")
                self.hook("tool", tool="Bash", phase="before", call_id="background")
                self.hook("tool", tool="Bash", phase="after", call_id="background", background=True)
                target.write_text("B")
                self.hook("tool", tool="Edit", paths=["notes.txt"], phase="before", call_id="direct")
                target.write_text("C")
                self.hook("tool", tool="Edit", paths=["notes.txt"], phase="after", call_id="direct")
                self.hook("tool", tool="Bash", phase="complete", call_id="background")

                target.write_text(restored)

                actual = self.hook("stop", answer="restored")
                self.assertEqual(bool(actual.get("block")), should_block, actual)

    def test_SHOULD_keep_a_clean_shell_baseline_unknown_when_a_later_capture_observes_edits(self):
        for restored, should_block in (("readme\n", False), ("B", True)):
            with self.subTest(restored=restored):
                target = self.repo / "README.md"
                target.write_text("readme\n")
                self.set_card()
                self.mark("D1")
                self.mark("D2")
                self.hook("tool", tool="Bash", phase="before", call_id="long")
                target.write_text("B")
                self.hook("tool", tool="Edit", paths=["README.md"], phase="before", call_id="short")
                target.write_text("C")
                self.hook("tool", tool="Edit", paths=["README.md"], phase="after", call_id="short")
                self.hook("tool", tool="Bash", phase="after", call_id="long")

                target.write_text(restored)

                actual = self.hook("stop", answer="restored")
                self.assertEqual(bool(actual.get("block")), should_block, actual)

    def test_SHOULD_keep_an_absent_shell_baseline_unknown_when_a_later_capture_observes_a_new_file(self):
        target = self.repo / "notes.txt"
        self.set_card()
        self.mark("D1")
        self.mark("D2")
        self.hook("tool", tool="Bash", phase="before", call_id="long")
        target.write_text("B")
        self.hook("tool", tool="Edit", paths=["notes.txt"], phase="before", call_id="short")
        target.write_text("C")
        self.hook("tool", tool="Edit", paths=["notes.txt"], phase="after", call_id="short")
        self.hook("tool", tool="Bash", phase="after", call_id="long")

        target.unlink()

        self.assertEqual(self.hook("stop", answer="restored"), {})
        target.write_text("B")
        self.assertIn("notes.txt", self.hook("stop", answer="intermediate").get("block", ""))

    def test_SHOULD_preserve_direct_baselines_for_ignored_files_during_a_shell_call(self):
        (self.repo / ".gitignore").write_text("notes.txt\n")
        target = self.repo / "notes.txt"
        target.write_text("A")
        self.set_card()
        self.mark("D1")
        self.mark("D2")
        self.hook("tool", tool="Bash", phase="before", call_id="long")
        self.hook("tool", tool="Edit", paths=["notes.txt"], phase="before", call_id="direct")

        target.write_text("B")

        self.hook("tool", tool="Edit", paths=["notes.txt"], phase="after", call_id="direct")
        self.hook("tool", tool="Bash", phase="after", call_id="long")
        self.assertIn("notes.txt", self.hook("stop", answer="changed").get("block", ""))
        target.write_text("A")
        self.assertEqual(self.run_task("card", "set", stdin=CARD).returncode, 0)
        self.assertEqual(self.hook("stop", answer="restored"), {})

    def test_SHOULD_retain_direct_creation_of_an_initially_absent_ignored_file(self):
        (self.repo / ".gitignore").write_text("notes.txt\n")
        target = self.repo / "notes.txt"
        self.set_card()
        self.mark("D1")
        self.mark("D2")
        self.hook("tool", tool="Bash", phase="before", call_id="long")
        self.hook("tool", tool="Write", paths=["notes.txt"], phase="before", call_id="direct")
        target.write_text("new content")
        self.hook("tool", tool="Write", paths=["notes.txt"], phase="after", call_id="direct")

        self.hook("tool", tool="Bash", phase="after", call_id="long")

        self.assertIn("notes.txt", self.hook("stop", answer="changed").get("block", ""))
        target.unlink()
        self.assertEqual(self.run_task("card", "set", stdin=CARD).returncode, 0)
        self.assertEqual(self.hook("stop", answer="restored"), {})

    def test_SHOULD_preserve_direct_baselines_for_git_metadata_during_a_shell_call(self):
        target = self.repo / ".git/config"
        original = target.read_text()
        self.set_card()
        self.mark("D1")
        self.mark("D2")
        self.hook("tool", tool="Bash", phase="before", call_id="long")
        self.hook("tool", tool="Edit", paths=[".git/config"], phase="before", call_id="direct")

        target.write_text(original + "\n[probe]\n    flag = true\n")

        self.hook("tool", tool="Edit", paths=[".git/config"], phase="after", call_id="direct")
        self.hook("tool", tool="Bash", phase="after", call_id="long")
        self.assertIn(".git/config", self.hook("stop", answer="changed").get("block", ""))
        target.write_text(original)
        self.assertEqual(self.run_task("card", "set", stdin=CARD).returncode, 0)
        self.assertEqual(self.hook("stop", answer="restored"), {})

    def test_SHOULD_preserve_direct_baselines_for_index_flags_that_hide_worktree_changes(self):
        for flag in ("--assume-unchanged", "--skip-worktree"):
            with self.subTest(flag=flag):
                target = self.repo / "README.md"
                target.write_text("readme\n")
                subprocess.run(
                    ["git", "update-index", "--no-assume-unchanged", "README.md"],
                    cwd=self.repo,
                    env=self.env,
                    check=True,
                )
                subprocess.run(
                    ["git", "update-index", "--no-skip-worktree", "README.md"], cwd=self.repo, env=self.env, check=True
                )
                subprocess.run(["git", "update-index", flag, "README.md"], cwd=self.repo, env=self.env, check=True)
                self.set_card()
                self.mark("D1")
                self.mark("D2")
                self.hook("tool", tool="Bash", phase="before", call_id="long")
                self.hook("tool", tool="Edit", paths=["README.md"], phase="before", call_id="direct")

                target.write_text("unresolved direct edit\n")

                self.hook("tool", tool="Edit", paths=["README.md"], phase="after", call_id="direct")
                self.hook("tool", tool="Bash", phase="after", call_id="long")
                self.assertIn("README.md", self.hook("stop", answer="changed").get("block", ""))
                target.write_text("readme\n")
                self.assertEqual(self.run_task("card", "set", stdin=CARD).returncode, 0)
                self.assertEqual(self.hook("stop", answer="restored"), {})

    def test_SHOULD_keep_capture_time_baselines_when_index_visibility_changes(self):
        for flag, clear in (("--assume-unchanged", "--no-assume-unchanged"), ("--skip-worktree", "--no-skip-worktree")):
            with self.subTest(flag=flag):
                subprocess.run(
                    ["git", "update-index", "--no-assume-unchanged", "README.md"],
                    cwd=self.repo,
                    env=self.env,
                    check=True,
                )
                subprocess.run(
                    ["git", "update-index", "--no-skip-worktree", "README.md"], cwd=self.repo, env=self.env, check=True
                )
                target = self.repo / "README.md"
                target.write_text("A")
                subprocess.run(["git", "update-index", flag, "README.md"], cwd=self.repo, env=self.env, check=True)
                self.set_card()
                self.mark("D1")
                self.mark("D2")
                self.hook("tool", tool="Bash", phase="before", call_id="long")
                self.hook("tool", tool="Edit", paths=["README.md"], phase="before", call_id="direct")
                target.write_text("B")
                self.hook("tool", tool="Edit", paths=["README.md"], phase="after", call_id="direct")

                subprocess.run(["git", "update-index", clear, "README.md"], cwd=self.repo, env=self.env, check=True)
                self.hook("tool", tool="Bash", phase="after", call_id="long")
                target.write_text("A")

                self.assertEqual(self.hook("stop", answer="restored"), {})

    def test_SHOULD_keep_capture_time_baselines_when_ignored_content_becomes_visible(self):
        ignore = self.repo / ".gitignore"
        ignore.write_text("notes.txt\n")
        target = self.repo / "notes.txt"
        target.write_text("A")
        self.set_card(CARD.replace("src/, tests/*.py", "src/, tests/*.py, .gitignore"))
        self.mark("D1")
        self.mark("D2")
        self.hook("tool", tool="Bash", phase="before", call_id="long")
        self.hook("tool", tool="Edit", paths=["notes.txt"], phase="before", call_id="direct")
        target.write_text("B")
        self.hook("tool", tool="Edit", paths=["notes.txt"], phase="after", call_id="direct")

        ignore.write_text("")
        self.hook("tool", tool="Bash", phase="after", call_id="long")
        target.write_text("A")

        self.assertEqual(self.hook("stop", answer="restored"), {})

    def test_SHOULD_discard_captures_without_frozen_discovery_exclusions(self):
        self.set_card()
        self.mark("D1")
        self.mark("D2")
        self.hook("tool", tool="Bash", phase="before", call_id="old")
        state_path = next(self.store.glob("*/state.json"))
        state = json.loads(state_path.read_text())
        turn = state["turns"]["s1"]
        turn["snapshot_version"] = 3
        turn["pending"]["old"]["excluded"] = turn["pending"]["old"].pop("domain")["excluded"]
        turn["background"]["old-background"] = dict(turn["pending"]["old"])
        state_path.write_text(json.dumps(state))

        self.assertEqual(self.hook("tool", tool="Bash", phase="after", call_id="old"), {})
        self.assertEqual(self.hook("stop", answer="unchanged"), {})
        state = json.loads(state_path.read_text())
        self.assertNotIn("old-background", state["turns"]["s1"]["background"])
        card = json.loads(self.run_task("card", "show", "--json").stdout)
        self.assertEqual([item["status"] for item in card["done"]], ["checked", "checked"])

    def test_SHOULD_include_a_staged_rename_source_in_scope_checks(self):
        target = self.repo / "outside.txt"
        target.write_text("A")
        subprocess.run(["git", "add", "outside.txt"], cwd=self.repo, env=self.env, check=True)
        subprocess.run(
            ["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "fixture"],
            cwd=self.repo,
            env=self.env,
            check=True,
        )
        (self.repo / "src").mkdir()
        self.set_card()
        self.mark("D1")
        self.mark("D2")
        self.hook("tool", tool="Bash", phase="before", call_id="move")

        subprocess.run(["git", "mv", "outside.txt", "src/moved.txt"], cwd=self.repo, env=self.env, check=True)

        actual = self.hook("tool", tool="Bash", phase="after", call_id="move")
        self.assertIn("outside.txt", actual.get("note", ""))
        self.assertIn("outside.txt", self.hook("stop", answer="done").get("block", ""))

    def test_SHOULD_ignore_staging_a_preexisting_rename_without_content_changes(self):
        (self.repo / "renamed.md").write_bytes((self.repo / "README.md").read_bytes())
        (self.repo / "README.md").unlink()
        self.set_card()
        self.hook("tool", tool="Bash", phase="before", call_id="stage")

        subprocess.run(["git", "add", "--all"], cwd=self.repo, env=self.env, check=True)

        self.assertEqual(self.hook("tool", tool="Bash", phase="after", call_id="stage"), {})
        self.assertEqual(self.hook("stop", answer="no content changes"), {})

    def test_SHOULD_discard_old_snapshot_formats_without_losing_the_card(self):
        target = self.repo / "notes.txt"
        target.write_text("A")
        self.set_card()
        self.mark("D1")
        state_path = next(self.store.glob("*/state.json"))
        state = json.loads(state_path.read_text())
        turn = state["turns"]["s1"]
        turn.pop("snapshot_version", None)
        turn["pending"] = {"old-call": {"notes.txt": "U1:1"}}
        turn["background"] = {"old-job": {"notes.txt": "U1:1"}}
        state_path.write_text(json.dumps(state))
        self.hook("tool", tool="Bash", phase="before", call_id="new-call")

        target.write_text("B")

        actual = self.hook("tool", tool="Bash", phase="after", call_id="new-call")
        self.assertIn("notes.txt", actual.get("note", ""))
        card = json.loads(self.run_task("card", "show", "--json").stdout)
        self.assertEqual(card["done"][0]["status"], "checked")

    def test_SHOULD_upgrade_versioned_scalar_baselines_without_losing_completed_checks(self):
        target = self.repo / "notes.txt"
        target.write_text("A")
        self.set_card()
        self.mark("D1")
        self.mark("D2")
        self.hook("tool", tool="Edit", paths=["notes.txt"], phase="before", call_id="old")
        target.write_text("B")
        self.hook("tool", tool="Edit", paths=["notes.txt"], phase="after", call_id="old")
        state_path = next(self.store.glob("*/state.json"))
        state = json.loads(state_path.read_text())
        turn = state["turns"]["s1"]
        turn["snapshot_version"] = 1
        turn["originals"] = {path: saved["state"] for path, saved in turn["originals"].items()}
        state_path.write_text(json.dumps(state))

        actual = self.hook("stop", answer="still changed")

        self.assertIn("notes.txt", actual.get("block", ""))
        card = json.loads(self.run_task("card", "show", "--json").stdout)
        self.assertEqual([item["status"] for item in card["done"]], ["checked", "checked"])

    def test_SHOULD_detect_untracked_deletion_and_readdition(self):
        self.set_card()
        target = self.repo / "éxport.txt"
        target.write_text("old")
        self.hook("tool", tool="Bash", phase="before", call_id="delete")
        target.unlink()
        self.assertIn("éxport.txt", self.hook("tool", tool="Bash", phase="after", call_id="delete")["note"])
        self.hook("tool", tool="Bash", phase="before", call_id="add")
        target.write_text("new")
        self.assertIn("éxport.txt", self.hook("tool", tool="Bash", phase="after", call_id="add")["note"])
        self.assertIn("D1", self.hook("stop", answer="done")["block"])

    def test_SHOULD_resolve_a_symlink_named_in_scope(self):
        (self.repo / "src").mkdir()
        (self.repo / "alias").symlink_to(self.repo / "src", target_is_directory=True)
        self.set_card(CARD.replace("src/, tests/*.py", "alias/"))
        self.assertEqual(self.run_task("scope", "check", "alias/éxport.py").returncode, 0)

    def test_SHOULD_share_preferences_between_worktrees_of_one_repository(self):
        other = Path(self.tmp.name) / "branch"
        subprocess.run(
            ["git", "-C", str(self.repo), "worktree", "add", "-qb", "test", str(other)], check=True, env=self.env
        )
        self.run_task("pref", "add", "one repository rule")
        self.assertIn("one repository rule", self.run_task("pref", "list", cwd=other).stdout)

    def test_SHOULD_capture_codex_shell_changes_with_tool_use_id(self):
        self.set_card()
        base = {"session_id": "s1", "cwd": str(self.repo), "tool_name": "Bash", "tool_use_id": "c1"}
        self.hook("codex", **base, hook_event_name="PreToolUse", tool_input={"command": "write file"})
        (self.repo / "README.md").write_text("changed")
        result = self.hook("codex", **base, hook_event_name="PostToolUse", tool_input={"command": "write file"})
        self.assertIn("README.md", result["hookSpecificOutput"]["additionalContext"])

    def test_SHOULD_preserve_concurrent_session_registrations(self):
        with ThreadPoolExecutor(max_workers=10) as pool:
            list(pool.map(lambda i: self.hook("prompt", session=f"s{i}", text="hi"), range(10)))
        state = json.loads(next(self.store.glob("*/state.json")).read_text())
        self.assertEqual(len(state["sessions"]), 10)

    def test_SHOULD_manage_preferences_while_multiple_sessions_are_active(self):
        self.hook("prompt", session="a", text="one")
        self.hook("prompt", session="b", text="two")
        added = self.run_task("pref", "add", "shared repository rule")
        self.assertEqual(added.returncode, 0, added.stderr)
        self.assertIn("shared repository rule", self.run_task("pref", "list").stdout)

    def test_SHOULD_read_cards_without_write_access_or_creating_a_store(self):
        self.set_card()
        lock = next(self.store.glob("*/.lock"))
        lock.chmod(0o444)
        shown = self.run_task("card", "show", "--session", "s1")
        self.assertEqual(shown.returncode, 0, shown.stderr)
        self.assertIn("D1", self.run_task("status", "--session", "s1").stdout)
        self.assertEqual(self.run_task("scope", "check", "src/a.py", "--session", "s1").returncode, 0)
        self.assertEqual(self.run_task("pref", "list").returncode, 0)
        self.assertEqual(self.run_task("steering").returncode, 0)
        empty = Path(self.tmp.name) / "absent-store"
        self.env["AGENT_TASK_DIR"] = str(empty)
        self.assertEqual(self.run_task("pref", "list").returncode, 0)
        self.assertFalse(empty.exists())

    def test_SHOULD_track_background_shell_writes_at_completion_across_prompts(self):
        self.set_card()
        self.hook("tool", tool="bash", phase="before", call_id="async-1")
        self.hook("tool", tool="bash", phase="after", call_id="async-1", background=True)
        self.hook("prompt", text="keep going")
        (self.repo / "README.md").write_text("background command changed it")
        self.assertEqual(self.hook("tool", tool="Read", paths=["README.md"]), {})
        complete = self.hook("tool", tool="bash", phase="complete", call_id="async-1")
        self.assertIn("README.md", complete.get("note", ""))
        self.assertIn("D1", self.hook("stop", answer="done")["block"])
        self.hook("prompt", text="explain the result")
        (self.repo / "README.md").write_text("the user now changes it")
        self.assertEqual(self.hook("tool", tool="bash", phase="complete", call_id="async-1"), {})
        self.assertEqual(self.hook("stop", answer="explained"), {})

    def test_SHOULD_accept_background_completion_before_the_start_result(self):
        self.set_card()
        self.hook("tool", tool="eval", phase="before", call_id="fast-job")
        (self.repo / "README.md").write_text("finished quickly")
        self.assertIn("README.md", self.hook("tool", tool="eval", phase="complete", call_id="fast-job")["note"])
        self.hook("tool", tool="eval", phase="after", call_id="fast-job", background=True)
        state = json.loads(next(self.store.glob("*/state.json")).read_text())
        self.assertEqual(state["turns"]["s1"]["steps"], 1)
        self.assertFalse(state["turns"]["s1"].get("background"))

    def test_SHOULD_complete_a_background_shell_by_its_task_id(self):
        self.set_card()
        self.hook("tool", tool="Bash", phase="before", call_id="bash-call")
        self.hook("tool", tool="Bash", phase="after", call_id="bash-call", background=True, background_id="job-1")
        self.hook("prompt", text="keep going")
        (self.repo / "README.md").write_text("background write")
        complete = self.hook("tool", tool="Bash", phase="complete", call_id="get-task-call", background_id="job-1")
        self.assertIn("README.md", complete.get("note", ""))
        self.assertIn("D1", self.hook("stop", answer="done")["block"])
        self.hook("prompt", text="explain")
        (self.repo / "README.md").write_text("user write after completion")
        self.assertEqual(
            self.hook("tool", tool="Bash", phase="complete", call_id="bash-call", background_id="job-1"), {}
        )
        self.assertEqual(self.hook("stop", answer="explained"), {})

    def test_SHOULD_report_shell_writes_at_background_handoff(self):
        self.set_card()
        self.hook("tool", tool="Bash", phase="before", call_id="bash-call")
        (self.repo / "README.md").write_text("wrote before handoff")
        handoff = self.hook("tool", tool="Bash", phase="after", call_id="bash-call", background=True)
        self.assertIn("README.md", handoff.get("note", ""))
        self.hook("prompt", text="keep going")
        self.assertEqual(self.hook("tool", tool="Bash", phase="complete", call_id="bash-call"), {})
        self.assertEqual(self.hook("stop", answer="explained"), {})

    def test_SHOULD_observe_final_response_bound_shell_writes_at_stop(self):
        self.set_card()
        self.hook("tool", tool="Bash", phase="before", call_id="bash-call")
        self.hook("tool", tool="Bash", phase="after", call_id="bash-call", background=True, until_stop=True)
        (self.repo / "README.md").write_text("wrote after handoff, before final response")
        stopped = self.hook("stop", answer="done")
        self.assertIn("README.md", stopped.get("block", ""))
        self.assertIn("D1", stopped.get("block", ""))
        self.hook("prompt", text="new turn after background process ended")
        (self.repo / "README.md").write_text("user changed it")
        self.assertEqual(self.hook("stop", answer="explained"), {})


if __name__ == "__main__":
    unittest.main()
