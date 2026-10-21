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
        self.env = {k: v for k, v in os.environ.items() if k != "AGENT_TASK_SESSION" and not k.startswith("GIT_CONFIG")}
        self.env.update(
            AGENT_TASK_DIR=str(self.store),
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
            self.run_task("check", item, "--evidence", "ran it")
        block = self.hook("stop", answer="done")["block"]
        self.assertIn("docs/x.md", block)

        self.run_task("scope", "add", "docs/x.md", "--reason", "the button needs a doc link")
        self.assertEqual(self.hook("stop", answer="done"), {})

    def test_SHOULD_ignore_files_already_dirty_when_the_card_was_set(self):
        (self.repo / "README.md").write_text("changed before the task\n")
        self.set_card()
        self.hook("tool", tool="Edit", paths=["src/app.py"])
        for item in ("D1", "D2"):
            self.run_task("check", item, "--evidence", "ran it")
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
        self.assertEqual(self.run_task("check", "D1", "--evidence", "ran it", "--session", "s1").returncode, 0)
        other = self.run_task("check", "D2", "--evidence", "ran it", "--session", "s2")
        self.assertIn("no card for session s2", other.stderr)
        self.assertIn("D2", self.run_task("status", "--session", "s1").stdout)

    def test_SHOULD_drop_item_ids_the_agent_wrote_into_the_card(self):
        saved = self.set_card(CARD.replace("- the button downloads a CSV", "- D1 the button downloads a CSV"))
        self.assertIn("- [ ] D1: the button downloads a CSV", saved.stdout)

    def test_SHOULD_send_the_stop_back_while_items_are_open_and_give_up_on_a_repeat(self):
        self.set_card()
        self.hook("tool", tool="Edit", paths=["src/app.py"])
        block = self.hook("stop", answer="all done")["block"]
        self.assertIn("D1: the button downloads a CSV", block)
        self.assertEqual(self.hook("stop", answer="all done"), {})

        self.hook("prompt", text="continue")
        self.hook("tool", tool="Edit", paths=["src/app.py"])
        self.run_task("check", "D1", "--evidence", "clicked it")
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
        self.run_task("check", "D1", "--evidence", "clicked it")
        rewritten = self.run_task("card", "set", stdin=CARD.replace("on the report page", "on the summary page"))
        self.assertIn("- [x] D1: the button downloads a CSV — clicked it", rewritten.stdout)

    def test_SHOULD_reopen_items_when_the_goal_changes(self):
        self.set_card()
        self.run_task("check", "D1", "--evidence", "clicked it")
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

    def test_SHOULD_measure_the_size_limit_on_the_agent_text_and_say_the_card_saved(self):
        self.set_card()
        self.add_scope_changes(30)
        for item in ("D1", "D2"):
            self.run_task("check", item, "--evidence", "ran the export and opened the file " * 40)
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
        self.run_task("check", "d1", "--evidence", "ok")
        self.run_task("block", "D2", "--reason", "later")
        self.assertEqual(self.run_task("status").returncode, 0)
        self.assertEqual(self.run_task("check", "D9", "--evidence", "x").returncode, 1)

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
            self.run_task("check", item, "--evidence", "ran it")
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
        result = self.run_task("check", "D1", "--evidence", "wrong session")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("D1", self.run_task("status", "--session", "s1").stdout)

    def test_SHOULD_refuse_ambiguous_mutations_without_a_session(self):
        self.set_card()
        self.hook("prompt", session="s2", text="other task")
        result = self.run_task("check", "D1", "--evidence", "ambiguous")
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
