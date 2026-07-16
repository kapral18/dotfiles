#!/usr/bin/env python3
"""Tests for the ,palantir legion orchestrator.

Covers the deterministic machine (transition tables, guards), legion state I/O,
config resolution, composer classification, and the pane brief contract. Pure
stdlib; tmux is never required (transport is exercised through injected fakes).

Run: python3 scripts/test_palantir.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parent.parent
LIB = REPO / "home" / "exact_lib" / "exact_,palantir"
sys.path[:0] = [str(LIB)]

import composer  # noqa: E402
import dashboard  # noqa: E402
import legion_state  # noqa: E402
import machine  # noqa: E402
import palantir_config  # noqa: E402
import panes  # noqa: E402
import supervisor  # noqa: E402


def make_state(tmp: str) -> legion_state.LegionState:
    return legion_state.LegionState(Path(tmp))


ROLES = {
    "triage": {"harness": "copilot", "model": ""},
    "implement": {"harness": "copilot", "model": ""},
    "adversarial-review": {"harness": "pi", "model": ""},
    "coordinator": {"harness": "copilot", "model": ""},
}


def summon(state: legion_state.LegionState, **kwargs) -> dict:
    defaults = dict(goal="test goal", roles=ROLES, criteria=[])
    defaults.update(kwargs)
    return state.new_legion(**defaults)


class FamilyDiversityTests(unittest.TestCase):
    def test_reviewer_family_differs_from_implementer(self) -> None:
        """The adversarial-review role must never share the implement family."""
        same = {
            "implement": {"harness": "copilot", "model": ""},
            "adversarial-review": {"harness": "copilot", "model": ""},
        }
        with self.assertRaises(machine.MachineError):
            machine.resolve_roles(same)
        diverse = {
            "implement": {"harness": "copilot", "model": ""},
            "adversarial-review": {"harness": "pi", "model": ""},
        }
        resolved = machine.resolve_roles(diverse)
        self.assertNotEqual(resolved["implement"]["family"], resolved["adversarial-review"]["family"])

    def test_family_derivation_prefers_model_over_harness(self) -> None:
        self.assertEqual(machine.derive_family("copilot", "gpt-5.5"), "gpt")
        self.assertEqual(machine.derive_family("pi", "claude-sonnet-4.5"), "claude")
        self.assertEqual(machine.derive_family("copilot", ""), "gpt")
        self.assertEqual(machine.derive_family("pi", ""), "claude")
        with self.assertRaises(machine.MachineError):
            machine.derive_family("mystery", "")

    def test_summon_refuses_same_family_roles(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state = make_state(tmp)
            with self.assertRaises(machine.MachineError):
                summon(
                    state,
                    roles={
                        "implement": {"harness": "copilot", "model": ""},
                        "adversarial-review": {"harness": "copilot", "model": ""},
                    },
                )


class TransitionTableTests(unittest.TestCase):
    def _legion(self, stage: str, **extra) -> dict:
        manifest = {
            "id": "l1",
            "goal": "g",
            "stage": stage,
            "implement_attempts": 0,
            "max_implement_attempts": 3,
            "review_blockers": [],
            "criteria": [],
            "memory_packet_written": False,
        }
        manifest.update(extra)
        return manifest

    def test_happy_path_table(self) -> None:
        """triage -> implement -> adversarial_review -> verify -> cleared."""
        m = self._legion("triage")
        m, actions = machine.transition(m, {"kind": "stage_result", "stage": "triage", "verdict": "implement"})
        self.assertEqual(m["stage"], "implement")
        self.assertEqual(actions[0]["kind"], "start_stage")
        m, actions = machine.transition(m, {"kind": "stage_result", "stage": "implement", "verdict": "done"})
        self.assertEqual(m["stage"], "adversarial_review")
        m, actions = machine.transition(
            m, {"kind": "stage_result", "stage": "adversarial_review", "verdict": "done", "blockers": []}
        )
        self.assertEqual(m["stage"], "verify")
        self.assertEqual(actions, [{"kind": "run_verify"}])
        m, actions = machine.transition(m, {"kind": "criteria_report", "green": True, "failures": []})
        self.assertEqual(m["stage"], "cleared_for_human")

    def test_diagnosis_route(self) -> None:
        m = self._legion("triage")
        m, _ = machine.transition(m, {"kind": "stage_result", "stage": "triage", "verdict": "diagnose"})
        self.assertEqual(m["stage"], "diagnose")
        m, _ = machine.transition(m, {"kind": "stage_result", "stage": "diagnose", "verdict": "done"})
        self.assertEqual(m["stage"], "investigate")
        m, _ = machine.transition(m, {"kind": "stage_result", "stage": "investigate", "verdict": "done"})
        self.assertEqual(m["stage"], "implement")

    def test_cleared_for_human_requires_verify_pass(self) -> None:
        """No edge reaches cleared_for_human except a green verify.

        A red criteria report never clears; review blockers force implement
        before verify may even run; grant outside cleared refuses.
        """
        # Red verify does not clear.
        m = self._legion("verify")
        m, _ = machine.transition(m, {"kind": "criteria_report", "green": False, "failures": [{"text": "x"}]})
        self.assertNotEqual(m["stage"], "cleared_for_human")
        # Open blockers make a verify report an error, not a clearance.
        blocked = self._legion("verify", review_blockers=["b1"])
        with self.assertRaises(machine.MachineError):
            machine.transition(blocked, {"kind": "criteria_report", "green": True})
        # A review with blockers routes back to implement, never toward clear.
        m = self._legion("adversarial_review")
        m, _ = machine.transition(
            m, {"kind": "stage_result", "stage": "adversarial_review", "verdict": "done", "blockers": ["missing test"]}
        )
        self.assertEqual(m["stage"], "implement")
        # grant_clear from any non-cleared stage refuses.
        for stage in ("triage", "implement", "verify", "holding"):
            with self.assertRaises(machine.MachineError):
                machine.transition(self._legion(stage), {"kind": "grant_clear"})
        # The only entry: green verify with no blockers.
        m = self._legion("verify")
        m, _ = machine.transition(m, {"kind": "criteria_report", "green": True})
        self.assertEqual(m["stage"], "cleared_for_human")

    def test_verify_failure_returns_implementer_to_work(self) -> None:
        """A red verify returns implement with the failure evidence."""
        m = self._legion("verify")
        failures = [{"text": "criterion 1", "check": "false", "exit": 1}]
        m, actions = machine.transition(m, {"kind": "criteria_report", "green": False, "failures": failures})
        self.assertEqual(m["stage"], "implement")
        self.assertEqual(m["implement_attempts"], 1)
        start = [a for a in actions if a["kind"] == "start_stage"][0]
        self.assertEqual(start["stage"], "implement")
        self.assertEqual(start["brief"]["verify_failures"], failures)
        wakes = [a for a in actions if a["kind"] == "wake_coordinator"]
        self.assertEqual(wakes[0]["event"]["kind"], "verify_failed")

    def test_verify_budget_exhaustion_parks(self) -> None:
        m = self._legion("verify", implement_attempts=2, max_implement_attempts=3)
        m, actions = machine.transition(m, {"kind": "criteria_report", "green": False, "failures": []})
        self.assertEqual(m["stage"], "holding")
        self.assertEqual(m["holding"]["reason"], "verify-budget-exhausted")
        self.assertEqual(actions[0]["event"]["kind"], "budget_exhausted")

    def test_review_blockers_spend_the_implement_budget(self) -> None:
        """Each blockers>0 return to implement counts one shared budget attempt."""
        m = self._legion("adversarial_review")
        m, actions = machine.transition(
            m, {"kind": "stage_result", "stage": "adversarial_review", "verdict": "done", "blockers": ["b1"]}
        )
        self.assertEqual(m["stage"], "implement")
        self.assertEqual(m["implement_attempts"], 1)
        start = [a for a in actions if a["kind"] == "start_stage"][0]
        self.assertEqual(start["brief"]["review_blockers"], ["b1"])

    def test_review_budget_exhaustion_parks_instead_of_looping(self) -> None:
        """Blocker returns are bounded: an exhausted budget parks in holding."""
        m = self._legion("adversarial_review", implement_attempts=2, max_implement_attempts=3)
        m, actions = machine.transition(
            m, {"kind": "stage_result", "stage": "adversarial_review", "verdict": "done", "blockers": ["b1", "b2"]}
        )
        self.assertEqual(m["stage"], "holding")
        self.assertEqual(m["holding"]["reason"], "review-budget-exhausted")
        self.assertEqual(m["holding"]["resume_stage"], "implement")
        self.assertEqual(actions[0]["event"]["kind"], "budget_exhausted")
        self.assertEqual(actions[0]["event"]["blockers"], ["b1", "b2"])
        self.assertEqual(machine.attention_event(m), actions[0]["event"])

    def test_mixed_verify_and_review_returns_share_one_budget(self) -> None:
        """Two review returns plus one verify failure exhaust a budget of 3."""
        m = self._legion("adversarial_review", max_implement_attempts=3)
        blockers_event = {"kind": "stage_result", "stage": "adversarial_review", "verdict": "done", "blockers": ["b"]}
        m, _ = machine.transition(m, blockers_event)
        self.assertEqual((m["stage"], m["implement_attempts"]), ("implement", 1))
        m["stage"] = "adversarial_review"
        m, _ = machine.transition(m, blockers_event)
        self.assertEqual((m["stage"], m["implement_attempts"]), ("implement", 2))
        m["stage"] = "verify"
        m["review_blockers"] = []
        m, _ = machine.transition(m, {"kind": "criteria_report", "green": False, "failures": []})
        self.assertEqual(m["stage"], "holding")
        self.assertEqual(m["holding"]["reason"], "verify-budget-exhausted")

    def test_question_parks_and_answer_resumes(self) -> None:
        m = self._legion("implement")
        m, _ = machine.transition(m, {"kind": "question", "role": "implement", "text": "which db?"})
        self.assertEqual(m["stage"], "holding")
        m, actions = machine.transition(m, {"kind": "answer", "text": "postgres"})
        self.assertEqual(m["stage"], "implement")
        self.assertEqual(actions[0]["brief"]["answer"], "postgres")

    def test_triage_reject_parks(self) -> None:
        m = self._legion("triage")
        m, _ = machine.transition(m, {"kind": "stage_result", "stage": "triage", "verdict": "reject", "summary": "dup"})
        self.assertEqual(m["stage"], "holding")

    def test_terminal_stage_refuses_everything(self) -> None:
        m = self._legion("banished")
        with self.assertRaises(machine.MachineError):
            machine.transition(m, {"kind": "banish"})

    def test_review_result_without_blockers_field_refuses(self) -> None:
        """A review result must state blockers explicitly; omission fails closed."""
        m = self._legion("adversarial_review")
        with self.assertRaises(machine.MachineError):
            machine.transition(m, {"kind": "stage_result", "stage": "adversarial_review", "verdict": "done"})

    def test_question_while_holding_refuses(self) -> None:
        """A second question must not clobber the parked holding context."""
        m = self._legion("implement")
        m, _ = machine.transition(m, {"kind": "question", "role": "implement", "text": "q1"})
        with self.assertRaises(machine.MachineError):
            machine.transition(m, {"kind": "question", "role": "implement", "text": "q2"})
        self.assertEqual(m["holding"]["resume_stage"], "implement")

    def test_attention_event_mirrors_transition_wakes(self) -> None:
        """attention_event reconstructs the exact wake for parked/cleared stages."""
        m = self._legion("implement")
        m, actions = machine.transition(m, {"kind": "question", "role": "implement", "text": "which db?"})
        self.assertEqual(machine.attention_event(m), actions[0]["event"])
        cleared = self._legion("cleared_for_human")
        self.assertEqual(machine.attention_event(cleared), {"kind": "cleared_for_human"})
        self.assertIsNone(machine.attention_event(self._legion("implement")))
        self.assertEqual(machine.attention(self._legion("banished")), "orphan")
        self.assertIsNone(machine.attention(self._legion("banished", teardown_status="complete")))

    def test_attention_flags_erroring_transport_on_inflight_legions(self) -> None:
        """A dead coordinator transport is human-visible, not a silent retry loop."""
        erroring = {"status": "error", "last_error": "no tmux server"}
        m = self._legion("implement", coordinator_transport=erroring)
        self.assertEqual(machine.attention(m), "transport")
        # Parked/cleared/terminal states keep their own flag.
        self.assertEqual(machine.attention(self._legion("holding", coordinator_transport=erroring)), "holding")
        self.assertEqual(
            machine.attention(self._legion("banished", teardown_status="complete", coordinator_transport=erroring)),
            None,
        )
        self.assertIsNone(machine.attention(self._legion("implement", coordinator_transport={"status": "ready"})))

    def test_attention_flags_unrouted_memory_packet_until_marked_routed(self) -> None:
        """A closed legion with a persisted, unrouted packet stays visible."""
        closed = self._legion("banished", teardown_status="complete", memory_packet_written=True)
        self.assertEqual(machine.attention(closed), "unrouted")
        self.assertEqual(machine.summarize(closed)["attention"], "unrouted")
        routed = dict(closed, memory_packet_routed=True)
        self.assertIsNone(machine.attention(routed))
        self.assertTrue(machine.summarize(routed)["memory_packet_routed"])
        # An incomplete teardown outranks the unrouted flag.
        orphan = dict(closed, teardown_status="failed")
        self.assertEqual(machine.attention(orphan), "orphan")

    def test_stage_result_for_wrong_stage_refuses(self) -> None:
        m = self._legion("implement")
        with self.assertRaises(machine.MachineError):
            machine.transition(m, {"kind": "stage_result", "stage": "triage", "verdict": "implement"})


class MemoryRoutingTests(unittest.TestCase):
    def test_legion_close_routes_memory(self) -> None:
        """Closing emits exactly one three-layer memory-routing packet."""
        m = {
            "id": "l1",
            "goal": "g",
            "stage": "cleared_for_human",
            "worktree": "/wt",
            "memory_packet_written": False,
        }
        m, actions = machine.transition(m, {"kind": "grant_clear"})
        self.assertEqual(m["stage"], "banished")
        packets = [a for a in actions if a["kind"] == "route_memory"]
        self.assertEqual(len(packets), 1)
        self.assertEqual([a["kind"] for a in actions], ["route_memory"])
        routes = packets[0]["packet"]["routes"]
        self.assertIn(",ai-kb remember", routes["durable"])
        self.assertIn("/tmp/specs", routes["ephemeral"])
        self.assertIn("AGENTS.md", routes["repo"])
        # Idempotent: a second close (banish of a banished legion) refuses,
        # and memory_packet_written guards double packet creation.
        m2 = {"id": "l2", "goal": "g", "stage": "implement", "memory_packet_written": True}
        m2, actions2 = machine.transition(m2, {"kind": "banish"})
        self.assertEqual([a for a in actions2 if a["kind"] == "route_memory"], [])

    def test_banish_routes_memory_from_any_stage(self) -> None:
        m = {"id": "l1", "goal": "g", "stage": "implement", "memory_packet_written": False}
        m, actions = machine.transition(m, {"kind": "banish"})
        self.assertEqual(m["stage"], "banished")
        self.assertEqual(len([a for a in actions if a["kind"] == "route_memory"]), 1)


class WakeDedupeTests(unittest.TestCase):
    def test_identical_unresolved_condition_enqueues_once(self) -> None:
        obs, first = machine.dedupe_wake({}, "verify_failed", "fp1")
        self.assertTrue(first)
        obs, second = machine.dedupe_wake(obs, "verify_failed", "fp1")
        self.assertFalse(second)
        obs = machine.resolve_wake(obs, "verify_failed")
        _obs, recurred = machine.dedupe_wake(obs, "verify_failed", "fp1")
        self.assertTrue(recurred)

    def test_changed_fingerprint_enqueues(self) -> None:
        obs, _ = machine.dedupe_wake({}, "k", "fp1")
        _obs, again = machine.dedupe_wake(obs, "k", "fp2")
        self.assertTrue(again)


class DebrisGuardTests(unittest.TestCase):
    """Operations on nonexistent legions must not create lock-only debris dirs,
    and any surviving debris must stay visible and banishable."""

    def test_lock_refuses_to_create_missing_legion_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state = make_state(tmp)
            state.init()
            with self.assertRaises(SystemExit):
                with state.lock("ghost"):
                    pass
            self.assertEqual(list(state.legions_dir.iterdir()), [])

    def test_supervisor_acquire_refuses_missing_legion(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state = make_state(tmp)
            state.init()
            with self.assertRaises(SystemExit):
                supervisor.SupervisorLock(state, "ghost").acquire()
            self.assertEqual(list(state.legions_dir.iterdir()), [])

    def test_manifest_less_debris_is_visible_as_corrupt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state = make_state(tmp)
            state.init()
            (state.legions_dir / "debris1").mkdir()
            self.assertEqual(state.list_legions(), ["debris1"])
            rows = state.summaries()
            self.assertEqual([(r["id"], r["stage"]) for r in rows], [("debris1", "corrupt")])

    def test_remove_debris_removes_only_manifest_less_dirs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state = make_state(tmp)
            state.init()
            (state.legions_dir / "debris1").mkdir()
            manifest = summon(state)
            with self.assertRaises(SystemExit):
                legion_state.main(["--state-home", tmp, "remove-debris", manifest["id"]])
            self.assertEqual(legion_state.main(["--state-home", tmp, "remove-debris", "debris1"]), 0)
            self.assertFalse((state.legions_dir / "debris1").exists())
            self.assertTrue(state.manifest_path(manifest["id"]).exists())

    def test_dashboard_allows_banish_on_corrupt_rows(self) -> None:
        self.assertTrue(dashboard.action_available("corrupt", "banish"))
        self.assertFalse(dashboard.action_available("corrupt", "send-word"))
        self.assertFalse(dashboard.action_available("corrupt", "grant"))


class LegionStateTests(unittest.TestCase):
    def test_new_legion_persists_and_lists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state = make_state(tmp)
            manifest = summon(state, goal="ship the thing", git_root="/repo", worktree="/repo/legion")
            self.assertEqual(state.list_legions(), [manifest["id"]])
            loaded = state.load(manifest["id"])
            self.assertEqual(loaded["goal"], "ship the thing")
            self.assertEqual(loaded["stage"], "summon")
            self.assertTrue(loaded["owns_worktree"])
            self.assertEqual((state.legion_dir(manifest["id"]) / "goal.txt").read_text(), "ship the thing")

    def test_legion_does_not_own_repository_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state = make_state(tmp)
            manifest = summon(state, git_root="/repo", worktree="/repo")
            self.assertFalse(manifest["owns_worktree"])

    def test_apply_event_is_locked_and_persisted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state = make_state(tmp)
            manifest = summon(state)
            state.save({**manifest, "stage": "triage"})
            new_manifest, _ = state.apply_event(
                manifest["id"], {"kind": "stage_result", "stage": "triage", "verdict": "implement"}
            )
            self.assertEqual(new_manifest["stage"], "implement")
            self.assertEqual(state.load(manifest["id"])["stage"], "implement")

    def test_mark_routed_requires_a_closed_legion_with_a_packet(self) -> None:
        """mark-routed flips memory_packet_routed only on a banished legion with a persisted packet."""
        with tempfile.TemporaryDirectory() as tmp:
            state = make_state(tmp)
            manifest = summon(state)
            env = {**os.environ, "PALANTIR_STATE_HOME": tmp}
            argv = ["python3", str(LIB / "legion_state.py"), "mark-routed", manifest["id"]]
            proc = subprocess.run(argv, env=env, capture_output=True, text=True)
            self.assertEqual(proc.returncode, 1)
            self.assertIn("not closed", proc.stderr)
            state.save({**state.load(manifest["id"]), "stage": "banished"})
            proc = subprocess.run(argv, env=env, capture_output=True, text=True)
            self.assertEqual(proc.returncode, 1)
            self.assertIn("no persisted memory packet", proc.stderr)
            state.save({**state.load(manifest["id"]), "memory_packet_written": True, "teardown_status": "complete"})
            proc = subprocess.run(argv, env=env, capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0)
            self.assertTrue(state.load(manifest["id"])["memory_packet_routed"])
            self.assertIsNone(machine.attention(state.load(manifest["id"])))

    def test_corrupt_manifest_reports_not_widens(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state = make_state(tmp)
            manifest = summon(state)
            state.manifest_path(manifest["id"]).write_text("{broken", encoding="utf-8")
            with self.assertRaises(SystemExit):
                state.load(manifest["id"])
            rows = state.summaries()
            self.assertEqual(rows[0]["stage"], "corrupt")
            self.assertEqual(rows[0]["attention"], "corrupt")

    def test_unknown_manifest_stage_is_reported_as_corrupt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state = make_state(tmp)
            manifest = summon(state)
            state.save({**manifest, "stage": "disbanded"})
            row = state.summaries()[0]
            self.assertEqual(row["stage"], "corrupt")
            self.assertEqual(row["invalid_stage"], "disbanded")

    def test_new_legion_refuses_malformed_criteria(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state = make_state(tmp)
            for criteria in ({"text": "not a list"}, ["not an object"], [{"text": "", "check": "true"}]):
                with self.subTest(criteria=criteria), self.assertRaises(machine.MachineError):
                    summon(state, criteria=criteria)

    def test_summarize_counts_criteria(self) -> None:
        m = {"id": "x", "stage": "verify", "criteria": [{"status": "green"}, {"status": "red"}]}
        row = machine.summarize(m)
        self.assertEqual((row["criteria_green"], row["criteria_total"]), (1, 2))


class VerifyRunnerTests(unittest.TestCase):
    def test_run_criteria_executes_checks_from_worktree(self) -> None:
        with tempfile.TemporaryDirectory() as wt:
            Path(wt, "marker").write_text("x")
            manifest = {
                "worktree": wt,
                "criteria": [
                    {"text": "marker exists", "check": "test -f marker"},
                    {"text": "never", "check": "test -f missing"},
                    {"text": "judgment only"},
                ],
            }
            report = supervisor.run_criteria(manifest)
            self.assertFalse(report["green"])
            self.assertEqual(report["checked"], 2)
            self.assertEqual(len(report["failures"]), 1)
            self.assertEqual(manifest["criteria"][0]["status"], "green")
            self.assertEqual(manifest["criteria"][1]["status"], "red")
            self.assertNotIn("status", manifest["criteria"][2])

    def test_run_criteria_times_out_hanging_checks_as_red(self) -> None:
        """A hanging criterion check is bounded and reported red, never waited on forever."""
        with tempfile.TemporaryDirectory() as wt:
            manifest = {
                "worktree": wt,
                "criteria": [{"text": "hangs", "check": "sleep 60"}],
            }
            with mock.patch.object(supervisor, "CHECK_TIMEOUT_SECS", 0.2):
                report = supervisor.run_criteria(manifest)
            self.assertFalse(report["green"])
            self.assertEqual(report["failures"][0]["exit"], 124)
            self.assertIn("timed out", report["failures"][0]["output"])
            self.assertEqual(manifest["criteria"][0]["status"], "red")

    def test_verify_pass_feeds_machine_and_returns_implement(self) -> None:
        """End-to-end: red check -> criteria_report -> implement return action."""
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as wt:
            state = make_state(tmp)
            manifest = summon(state, criteria=[{"text": "missing", "check": "test -f missing"}])
            state.save({**state.load(manifest["id"]), "stage": "verify", "worktree": wt})
            sup = supervisor.Supervisor(state, manifest["id"], config=dict(palantir_config.DEFAULTS))
            with mock.patch.object(sup, "execute_pending"):
                report = sup.verify_pass()
            self.assertFalse(report["green"])
            self.assertEqual(state.load(manifest["id"])["stage"], "implement")
            pending = state.load(manifest["id"])["pending_actions"]
            self.assertTrue(any(a["kind"] == "start_stage" and a["stage"] == "implement" for a in pending))


class SupervisorLoopTests(unittest.TestCase):
    def test_workspace_delta_isolates_paths_changed_during_stage(self) -> None:
        with tempfile.TemporaryDirectory() as wt:
            subprocess.run(["git", "init", "-q", wt], check=True)
            tracked = Path(wt, "existing.txt")
            tracked.write_text("before\n", encoding="utf-8")
            before = supervisor.workspace_snapshot(wt)
            tracked.write_text("after\n", encoding="utf-8")
            Path(wt, "new.txt").write_text("new\n", encoding="utf-8")
            delta = supervisor.workspace_delta(before, supervisor.workspace_snapshot(wt))
            self.assertEqual(delta["changed_paths"], ["existing.txt", "new.txt"])

    def test_pending_action_survives_failed_side_effect_and_retries_once(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state = make_state(tmp)
            manifest = summon(state)
            state.save({**state.load(manifest["id"]), "stage": "triage"})
            state.apply_event(
                manifest["id"],
                {"kind": "stage_result", "stage": "triage", "verdict": "implement"},
            )
            sup = supervisor.Supervisor(state, manifest["id"], config=dict(palantir_config.DEFAULTS))
            with (
                mock.patch.object(sup, "begin_stage"),
                mock.patch.object(
                    panes,
                    "start_stage",
                    side_effect=[panes.PaneError("not ready"), {"injected": True}],
                ) as start_stage,
            ):
                self.assertFalse(sup.execute_pending())
                self.assertEqual(len(state.load(manifest["id"])["pending_actions"]), 1)
                self.assertTrue(sup.execute_pending())
            self.assertEqual(start_stage.call_count, 2)
            self.assertEqual(state.load(manifest["id"])["pending_actions"], [])

    def test_delivered_stage_action_removes_retry_brief(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state = make_state(tmp)
            manifest = summon(state)
            brief_path = state.stages_dir(manifest["id"]) / "triage.brief.json"
            brief_path.parent.mkdir(parents=True)
            brief_path.write_text("{}\n", encoding="utf-8")
            sup = supervisor.Supervisor(state, manifest["id"], config=dict(palantir_config.DEFAULTS))
            with (
                mock.patch.object(sup, "begin_stage"),
                mock.patch.object(
                    panes,
                    "start_stage",
                    return_value={"injected": False, "already_delivered": True},
                ),
            ):
                self.assertTrue(
                    sup.execute_action({"kind": "start_stage", "stage": "triage", "brief": {}, "_action_id": "a1"})
                )
            self.assertFalse(brief_path.exists())

    def test_stage_baseline_recovers_after_crash_between_manifest_and_file_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state = make_state(tmp)
            manifest = summon(state)
            state.save(
                {
                    **manifest,
                    "stage": "triage",
                    "stage_runs": {"triage": 1},
                    "active_stage_run": {"stage": "triage", "run": 1, "action_id": "a1"},
                }
            )
            sup = supervisor.Supervisor(state, manifest["id"], config=dict(palantir_config.DEFAULTS))
            with mock.patch.object(supervisor, "workspace_snapshot", return_value={"files": {}}):
                sup.begin_stage("triage", "a1")
            baseline = state.stages_dir(manifest["id"]) / "triage.1.baseline.json"
            self.assertTrue(baseline.is_file())
            self.assertEqual(state.load(manifest["id"])["stage_runs"], {"triage": 1})

    def test_replayed_verify_action_does_not_rerun_after_stage_advanced(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state = make_state(tmp)
            manifest = summon(state)
            state.save({**manifest, "stage": "implement"})
            sup = supervisor.Supervisor(state, manifest["id"], config=dict(palantir_config.DEFAULTS))
            with mock.patch.object(supervisor, "run_criteria") as run_criteria:
                self.assertTrue(sup.execute_action({"kind": "run_verify", "_action_id": "a1"}))
            run_criteria.assert_not_called()

    def test_agent_role_cannot_dispatch_human_only_events(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state = make_state(tmp)
            manifest = summon(state)
            state.save({**state.load(manifest["id"]), "stage": "cleared_for_human"})
            sup = supervisor.Supervisor(state, manifest["id"], config=dict(palantir_config.DEFAULTS))
            with mock.patch.dict(os.environ, {"PALANTIR_AGENT_ROLE": "coordinator"}):
                for event in ({"kind": "grant_clear"}, {"kind": "banish"}):
                    with self.assertRaisesRegex(machine.MachineError, "human-only"):
                        sup.dispatch_event(event)
            self.assertEqual(state.load(manifest["id"])["stage"], "cleared_for_human")

    def test_dispatch_event_executes_runtime_actions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state = make_state(tmp)
            manifest = summon(state)
            state.save(
                {
                    **state.load(manifest["id"]),
                    "stage": "holding",
                    "holding": {
                        "reason": "question",
                        "text": "which port?",
                        "resume_stage": "implement",
                    },
                }
            )
            sup = supervisor.Supervisor(state, manifest["id"], config=dict(palantir_config.DEFAULTS))
            with mock.patch.object(sup, "execute_pending") as execute_pending:
                updated = sup.dispatch_event({"kind": "answer", "text": "9200"})
            self.assertEqual(updated["stage"], "implement")
            execute_pending.assert_called_once_with()
            action = state.load(manifest["id"])["pending_actions"][0]
            self.assertEqual(action["kind"], "start_stage")
            self.assertEqual(action["brief"]["answer"], "9200")

    def test_route_memory_action_persists_packet(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state = make_state(tmp)
            manifest = summon(state)
            sup = supervisor.Supervisor(state, manifest["id"], config=dict(palantir_config.DEFAULTS))
            packet = machine.memory_routing_packet(manifest)
            with mock.patch.object(panes, "wake_coordinator", return_value=False) as wake:
                sup.execute([{"kind": "route_memory", "packet": packet}])
            persisted = json.loads((state.legion_dir(manifest["id"]) / "memory-routing.json").read_text())
            self.assertEqual(persisted, packet)
            self.assertTrue(state.load(manifest["id"])["memory_packet_written"])
            wake.assert_not_called()

    def test_single_supervisor_lock(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state = make_state(tmp)
            manifest = summon(state)
            lock_a = supervisor.SupervisorLock(state, manifest["id"])
            lock_a.acquire()
            try:
                lock_b = supervisor.SupervisorLock(state, manifest["id"])
                with self.assertRaises(RuntimeError):
                    lock_b.acquire()
                self.assertTrue(lock_a.alive())
            finally:
                lock_a.release()
            self.assertFalse(lock_a.alive())

    def test_stage_result_handshake_consumed_once(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state = make_state(tmp)
            manifest = summon(state)
            state.save({**state.load(manifest["id"]), "stage": "triage"})
            stages = state.stages_dir(manifest["id"])
            stages.mkdir(parents=True, exist_ok=True)
            (stages / "triage.result.json").write_text(json.dumps({"stage": "triage", "verdict": "implement"}))
            sup = supervisor.Supervisor(state, manifest["id"], config=dict(palantir_config.DEFAULTS))
            with mock.patch.object(sup, "execute"):
                consumed = sup.consume_stage_result(state.load(manifest["id"]))
            self.assertTrue(consumed)
            self.assertEqual(state.load(manifest["id"])["stage"], "implement")
            self.assertFalse((stages / "triage.result.json").exists())
            events = [json.loads(line) for line in (stages / "events.jsonl").read_text().splitlines()]
            self.assertEqual(events[0]["stage"], "triage")
            self.assertEqual(events[0]["verdict"], "implement")
            with mock.patch.object(sup, "execute"):
                self.assertFalse(sup.consume_stage_result(state.load(manifest["id"])))

    def test_question_handshake_parks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state = make_state(tmp)
            manifest = summon(state)
            state.save({**state.load(manifest["id"]), "stage": "implement"})
            stages = state.stages_dir(manifest["id"])
            stages.mkdir(parents=True, exist_ok=True)
            (stages / "implement.result.json").write_text(json.dumps({"kind": "question", "text": "which port?"}))
            sup = supervisor.Supervisor(state, manifest["id"], config=dict(palantir_config.DEFAULTS))
            with mock.patch.object(sup, "execute"):
                sup.consume_stage_result(state.load(manifest["id"]))
            loaded = state.load(manifest["id"])
            self.assertEqual(loaded["stage"], "holding")
            self.assertEqual(loaded["holding"]["text"], "which port?")

    def test_verify_pass_survives_concurrent_stage_change(self) -> None:
        """A stale criteria report (stage moved mid-verify) is refused, not fatal."""
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as wt:
            state = make_state(tmp)
            manifest = summon(state, criteria=[{"text": "ok", "check": "true"}])
            state.save({**state.load(manifest["id"]), "stage": "implement", "worktree": wt})
            sup = supervisor.Supervisor(state, manifest["id"], config=dict(palantir_config.DEFAULTS))
            report = sup.verify_pass()  # must not raise MachineError
            self.assertTrue(report["green"])
            self.assertEqual(state.load(manifest["id"])["stage"], "implement")

    def test_run_loop_survives_tick_exception(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state = make_state(tmp)
            manifest = summon(state)
            sup = supervisor.Supervisor(state, manifest["id"], config=dict(palantir_config.DEFAULTS))
            with mock.patch.object(sup, "tick", side_effect=RuntimeError("boom")):
                self.assertEqual(sup.run(once=True), 0)

    def test_summon_waits_for_delivered_coordinator_brief(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state = make_state(tmp)
            manifest = summon(state)
            sup = supervisor.Supervisor(state, manifest["id"], config=dict(palantir_config.DEFAULTS))
            with (
                mock.patch.object(panes, "start_coordinator", side_effect=panes.PaneError("not ready")),
                mock.patch.object(panes, "start_stage") as start_stage,
            ):
                sup.tick()
            self.assertEqual(state.load(manifest["id"])["stage"], "summon")
            start_stage.assert_not_called()

    def test_tick_resurfaces_attention_wake_after_blocked_pane(self) -> None:
        """A holding wake stays queued until the coordinator pane becomes idle."""
        with tempfile.TemporaryDirectory() as tmp:
            state = make_state(tmp)
            manifest = summon(state)
            state.save(
                {
                    **state.load(manifest["id"]),
                    "stage": "holding",
                    "holding": {"reason": "question", "role": "implement", "text": "q?", "resume_stage": "implement"},
                }
            )
            sup = supervisor.Supervisor(state, manifest["id"], config=dict(palantir_config.DEFAULTS))
            with (
                mock.patch.object(panes, "start_coordinator"),
                mock.patch.object(panes, "wake_coordinator", return_value=False),
            ):
                sup.tick()
            queued = state.load(manifest["id"])["pending_wakes"]
            self.assertEqual([item["key"] for item in queued], ["question"])
            with (
                mock.patch.object(panes, "start_coordinator"),
                mock.patch.object(panes, "wake_coordinator", return_value=True) as delivered,
            ):
                sup.tick()
                sup.tick()
            self.assertEqual(delivered.call_count, 1)
            self.assertEqual(state.load(manifest["id"])["pending_wakes"], [])

    def test_refused_stage_result_surfaces_transition_refused_wake(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state = make_state(tmp)
            manifest = summon(state)
            state.save({**state.load(manifest["id"]), "stage": "triage"})
            stages = state.stages_dir(manifest["id"])
            stages.mkdir(parents=True, exist_ok=True)
            (stages / "triage.result.json").write_text(json.dumps({"stage": "triage", "verdict": "bogus"}))
            sup = supervisor.Supervisor(state, manifest["id"], config=dict(palantir_config.DEFAULTS))
            with mock.patch.object(sup, "surface") as surface:
                consumed = sup.consume_stage_result(state.load(manifest["id"]))
            self.assertFalse(consumed)
            self.assertEqual(surface.call_args.args[0]["kind"], "transition_refused")

    def test_wake_queue_survives_blocked_pane_without_duplicate_delivery(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state = make_state(tmp)
            manifest = summon(state)
            sup = supervisor.Supervisor(state, manifest["id"], config=dict(palantir_config.DEFAULTS))
            with mock.patch.object(panes, "wake_coordinator", return_value=False) as blocked:
                sup.surface({"kind": "verify_failed", "attempt": 1})
                sup.surface({"kind": "verify_failed", "attempt": 1})
            self.assertEqual(blocked.call_count, 1)
            loaded = state.load(manifest["id"])
            self.assertEqual(len(loaded["pending_wakes"]), 1)
            self.assertEqual(loaded["coordinator_transport"]["status"], "blocked")
            with mock.patch.object(panes, "wake_coordinator", return_value=True) as delivered:
                sup.drain_wakes()
                sup.drain_wakes()
            self.assertEqual(delivered.call_count, 1)
            self.assertEqual(state.load(manifest["id"])["pending_wakes"], [])

    def test_answer_resolves_delivered_and_pending_question_wake(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state = make_state(tmp)
            manifest = summon(state)
            state.save(
                {
                    **state.load(manifest["id"]),
                    "stage": "holding",
                    "holding": {"reason": "question", "text": "q?", "resume_stage": "implement"},
                    "wake_observations": {"question": "fingerprint"},
                    "pending_wakes": [{"key": "question", "fingerprint": "fingerprint", "event": {}}],
                }
            )
            sup = supervisor.Supervisor(state, manifest["id"], config=dict(palantir_config.DEFAULTS))
            with mock.patch.object(sup, "execute"):
                sup.dispatch_event({"kind": "answer", "text": "a"})
            loaded = state.load(manifest["id"])
            self.assertNotIn("question", loaded["wake_observations"])
            self.assertEqual(loaded["pending_wakes"], [])


class GovernanceContractTests(unittest.TestCase):
    def test_regular_chat_sessions_work_normally_and_palantir_is_strictly_opt_in(self) -> None:
        sop = (REPO / "home/readonly_AGENTS.md").read_text()
        skill = (REPO / "home/exact_dot_agents/exact_skills/exact_k-palantir/readonly_SKILL.md").read_text()
        opt_in = (
            "MUST NOT propose, summon, or hand work to a legion unless the user "
            "explicitly asks to use Palantír in the current conversation"
        )
        self.assertIn(opt_in, sop)
        self.assertIn(opt_in, skill)
        self.assertIn("Task size, complexity, duration, or convenience never count as that request.", sop)
        self.assertNotIn("The chat agent is read-only over projects", sop)
        frontmatter = skill.split("---", 2)[1]
        self.assertIn("Use only when the user explicitly asks to use Palantír", frontmatter)
        self.assertNotIn("disable-model-invocation", frontmatter)


class PaneContractTests(unittest.TestCase):
    def test_public_cli_uses_lore_heavy_actions_without_legacy_aliases(self) -> None:
        help_result = subprocess.run(
            ["bash", str(LIB / "main.sh"), "--help"],
            cwd=REPO,
            capture_output=True,
            text=True,
            check=True,
        )
        for action in (
            "summon",
            "farsee",
            "behold",
            "send-word",
            "answer",
            "grant",
            "banish",
            "keep-watch",
            "trial",
        ):
            self.assertIn(action, help_result.stdout)
        for legacy in ("muster", "ls", "status", "nudge", "approve", "disband", "watch", "verify"):
            result = subprocess.run(
                ["bash", str(LIB / "main.sh"), legacy],
                cwd=REPO,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 1)
            self.assertIn(f"Unknown command '{legacy}'", result.stderr)

    def test_summon_uses_deployed_shared_library_path(self) -> None:
        source = (LIB / "summon.sh").read_text()
        self.assertIn("$SCRIPT_DIR/../shared/worktree_lib.sh", source)
        self.assertIn("$SCRIPT_DIR/../shared/bash_utils_lib.sh", source)

    def test_banish_removes_only_owned_worktrees(self) -> None:
        source = (LIB / "banish.sh").read_text()
        self.assertIn('owns_worktree="$(printf', source)
        self.assertIn('git -C "$git_root" worktree remove', source)
        self.assertIn('if [ "$owns_worktree" = "true" ]', source)

    def test_grant_preflights_then_tears_down_legion(self) -> None:
        source = (LIB / "main.sh").read_text()
        self.assertIn('bash "$SCRIPT_DIR/banish.sh" "$legion_id" --preflight', source)
        self.assertIn('bash "$SCRIPT_DIR/banish.sh" "$legion_id" --teardown-only', source)
        # Grant ends with the memory-routing reminder so the packet is never silently dropped.
        self.assertIn(",palantir routed $legion_id", source)

    def test_shared_no_worktree_legion_does_not_require_clean_repo_for_teardown(self) -> None:
        with tempfile.TemporaryDirectory() as repo, tempfile.TemporaryDirectory() as state_home:
            subprocess.run(["git", "init", "-q", repo], check=True)
            Path(repo, "dirty.txt").write_text("intentional\n", encoding="utf-8")
            state = make_state(state_home)
            manifest = summon(state, git_root=repo, worktree=repo)
            state.save({**manifest, "stage": "cleared_for_human"})
            proc = subprocess.run(
                ["bash", str(LIB / "banish.sh"), manifest["id"], "--preflight"],
                env={**os.environ, "PALANTIR_STATE_HOME": state_home},
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_grant_persists_closeout_packet_and_completes_teardown(self) -> None:
        with tempfile.TemporaryDirectory() as repo, tempfile.TemporaryDirectory() as state_home:
            subprocess.run(["git", "init", "-q", repo], check=True)
            state = make_state(state_home)
            manifest = summon(state, git_root=repo, worktree=repo)
            state.save({**manifest, "stage": "cleared_for_human"})
            proc = subprocess.run(
                ["bash", str(LIB / "main.sh"), "grant", manifest["id"]],
                env={**os.environ, "PALANTIR_STATE_HOME": state_home},
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            closed = state.load(manifest["id"])
            self.assertEqual(closed["stage"], "banished")
            self.assertTrue(closed["memory_packet_written"])
            self.assertEqual(closed["teardown_status"], "complete")
            self.assertTrue((state.legion_dir(manifest["id"]) / "memory-routing.json").exists())
            self.assertIn("granted and torn down", proc.stdout)

    def test_teardown_drains_closeout_action_left_by_interrupted_dispatch(self) -> None:
        with tempfile.TemporaryDirectory() as repo, tempfile.TemporaryDirectory() as state_home:
            subprocess.run(["git", "init", "-q", repo], check=True)
            state = make_state(state_home)
            manifest = summon(state, git_root=repo, worktree=repo)
            state.save({**manifest, "stage": "implement"})
            state.apply_event(manifest["id"], {"kind": "banish"})
            self.assertEqual(len(state.load(manifest["id"])["pending_actions"]), 1)
            proc = subprocess.run(
                ["bash", str(LIB / "banish.sh"), manifest["id"], "--teardown-only"],
                env={**os.environ, "PALANTIR_STATE_HOME": state_home},
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            closed = state.load(manifest["id"])
            self.assertEqual(closed["pending_actions"], [])
            self.assertTrue(closed["memory_packet_written"])
            self.assertEqual(closed["teardown_status"], "complete")

    def test_harness_argv_known_and_unknown(self) -> None:
        self.assertEqual(panes.harness_argv("copilot"), ["copilot", "--allow-all"])
        self.assertEqual(
            panes.harness_argv("claude", "claude-opus-4.5"),
            ["claude", "--dangerously-skip-permissions", "--model", "claude-opus-4.5"],
        )
        self.assertEqual(
            panes.harness_argv("pi", "anthropic/claude-opus-4.8"),
            ["pi", "--approve", "--model", "anthropic/claude-opus-4.8"],
        )
        with self.assertRaises(panes.PaneError):
            panes.harness_argv("mystery")

    def test_copilot_command_bypasses_fresh_worktree_trust_gate(self) -> None:
        command = panes.harness_command("copilot")
        self.assertEqual(command, "COPILOT_ALLOW_ALL=true copilot --allow-all")

    def test_coordinator_command_carries_agent_role(self) -> None:
        command = panes.harness_command("copilot", role="coordinator")
        self.assertEqual(
            command,
            "COPILOT_ALLOW_ALL=true PALANTIR_AGENT_ROLE=coordinator copilot --allow-all",
        )

    def test_agent_role_cannot_summon_grant_or_banish(self) -> None:
        env = {**os.environ, "PALANTIR_AGENT_ROLE": "coordinator"}
        for command in ("summon", "grant", "banish"):
            proc = subprocess.run(
                ["bash", str(LIB / "main.sh"), command, "not-a-legion"],
                cwd=REPO,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 1)
            self.assertIn("human-only", proc.stderr)

    def test_launch_agent_waits_for_shell_and_marker_prevents_relaunch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            marker = Path(tmp) / "agent.json"
            sent = []

            def fake_tmux(*args):
                sent.append(args)
                return subprocess.CompletedProcess(args, 0, "", "")

            with (
                mock.patch.object(panes, "ensure_window", return_value="%7"),
                mock.patch.object(panes, "pane_verdict", side_effect=["unknown", "empty"]),
                mock.patch.object(composer, "run_tmux", side_effect=fake_tmux),
                mock.patch.object(panes.time, "sleep"),
            ):
                target = panes.launch_agent(
                    "s",
                    "implement",
                    "/wt",
                    "copilot",
                    "gpt-5.6-sol",
                    marker_path=marker,
                    settle_secs=2,
                )
            self.assertEqual(target, "%7")
            self.assertTrue(marker.is_file())
            self.assertEqual(sent[0][:3], ("send-keys", "-t", "%7"))

            with (
                mock.patch.object(panes, "ensure_window", return_value="%7"),
                mock.patch.object(panes, "pane_current_command", return_value="node"),
                mock.patch.object(composer, "run_tmux") as run_tmux,
            ):
                panes.launch_agent(
                    "s",
                    "implement",
                    "/wt",
                    "copilot",
                    "gpt-5.6-sol",
                    marker_path=marker,
                    settle_secs=2,
                )
            run_tmux.assert_not_called()

    def test_launch_agent_relaunches_when_pane_fell_back_to_shell(self) -> None:
        """A dead harness (pane back at a shell) must never take the brief as keys."""
        with tempfile.TemporaryDirectory() as tmp:
            marker = Path(tmp) / "agent.json"
            delivered = Path(tmp) / "stage.delivered"
            marker.write_text("{}\n", encoding="utf-8")
            delivered.write_text("digest\n", encoding="utf-8")
            sent = []

            def fake_tmux(*args):
                sent.append(args)
                return subprocess.CompletedProcess(args, 0, "", "")

            with (
                mock.patch.object(panes, "ensure_window", return_value="%7"),
                mock.patch.object(panes, "pane_current_command", return_value="fish"),
                mock.patch.object(panes, "pane_verdict", return_value="empty"),
                mock.patch.object(composer, "run_tmux", side_effect=fake_tmux),
                mock.patch.object(panes.time, "sleep"),
            ):
                panes.launch_agent(
                    "s",
                    "implement",
                    "/wt",
                    "copilot",
                    "gpt-5.6-sol",
                    marker_path=marker,
                    settle_secs=2,
                    delivered_path=delivered,
                )
            self.assertTrue(marker.is_file())  # rewritten by the relaunch
            self.assertFalse(delivered.exists())  # brief must be re-injected
            self.assertEqual(sent[0][:3], ("send-keys", "-t", "%7"))

    def test_launch_agent_keeps_marker_when_shell_named_pane_is_busy(self) -> None:
        """A transient shell command label must not erase a live harness marker."""
        with tempfile.TemporaryDirectory() as tmp:
            marker = Path(tmp) / "agent.json"
            delivered = Path(tmp) / "stage.delivered"
            marker.write_text("{}\n", encoding="utf-8")
            delivered.write_text("digest\n", encoding="utf-8")
            with (
                mock.patch.object(panes, "ensure_window", return_value="%7"),
                mock.patch.object(panes, "pane_current_command", return_value="fish"),
                mock.patch.object(panes, "pane_verdict", return_value="pending"),
                mock.patch.object(composer, "run_tmux") as run_tmux,
            ):
                panes.launch_agent(
                    "s",
                    "implement",
                    "/wt",
                    "copilot",
                    "gpt-5.6-sol",
                    marker_path=marker,
                    settle_secs=2,
                    delivered_path=delivered,
                )
            self.assertTrue(marker.is_file())
            self.assertTrue(delivered.is_file())
            run_tmux.assert_not_called()

    def test_stage_brief_names_handshake_contract(self) -> None:
        legion = {
            "id": "l1",
            "goal": "fix the bug",
            "criteria": [{"text": "observable behavior", "check": "test -f outcome"}],
        }
        text = panes.stage_brief_text(legion, "adversarial_review", {"handoff": "done"}, Path("/tmp/x/result.json"))
        self.assertIn("adversarial-review", text)
        self.assertIn("/tmp/x/result.json", text)
        self.assertIn("blockers", text)
        self.assertIn("vacuous", text)
        self.assertIn("supervisor", text)
        self.assertIn("do not rerun the full acceptance suite", text.lower())
        triage = panes.stage_brief_text(legion, "triage", {}, Path("/r.json"))
        self.assertIn("implement|diagnose|reject", triage)
        implement = panes.stage_brief_text(legion, "implement", {}, Path("/r.json"))
        self.assertIn("supervisor", implement)
        self.assertIn("do not run the full acceptance suite", implement.lower())

    def test_stage_brief_retries_until_delivered_then_dedupes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state = make_state(tmp)
            manifest = summon(state)
            state.save({**state.load(manifest["id"]), "stage": "triage", "session": "legion-test"})
            with (
                mock.patch.object(panes, "launch_agent", return_value="%7"),
                mock.patch.object(panes, "inject_when_idle", side_effect=[False, True]) as inject,
            ):
                first = panes.start_stage(state, manifest["id"], "triage", {"attempt": 1})
                second = panes.start_stage(state, manifest["id"], "triage", {"attempt": 1})
                third = panes.start_stage(state, manifest["id"], "triage", {"attempt": 1})
            self.assertFalse(first["injected"])
            self.assertTrue(second["injected"])
            self.assertFalse(third["injected"])
            self.assertTrue(third["already_delivered"])
            self.assertEqual(inject.call_count, 2)
            self.assertTrue((state.stages_dir(manifest["id"]) / "triage.delivered").is_file())

    def test_failed_stage_launch_leaves_brief_for_supervisor_retry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state = make_state(tmp)
            manifest = summon(state)
            state.save({**state.load(manifest["id"]), "stage": "triage", "session": "legion-test"})
            with (
                mock.patch.object(panes, "launch_agent", side_effect=panes.PaneError("shell not ready")),
                self.assertRaises(panes.PaneError),
            ):
                panes.start_stage(state, manifest["id"], "triage", {"attempt": 1})
            brief = json.loads((state.stages_dir(manifest["id"]) / "triage.brief.json").read_text())
            self.assertEqual(brief, {"attempt": 1})

    def test_start_stage_retry_keeps_fresh_result_file(self) -> None:
        """The supervisor retry path must not delete a result the role just wrote."""
        with tempfile.TemporaryDirectory() as tmp:
            state = make_state(tmp)
            manifest = summon(state)
            state.save({**state.load(manifest["id"]), "stage": "triage", "session": "legion-test"})
            with (
                mock.patch.object(panes, "launch_agent", return_value="%7"),
                mock.patch.object(panes, "inject_when_idle", return_value=True),
            ):
                panes.start_stage(state, manifest["id"], "triage", {"attempt": 1})
                result = state.stages_dir(manifest["id"]) / "triage.result.json"
                result.write_text('{"stage": "triage", "verdict": "implement"}\n', encoding="utf-8")
                panes.start_stage(state, manifest["id"], "triage", {"attempt": 1})
            self.assertTrue(result.is_file())

    def test_summon_passes_configured_attempt_budget(self) -> None:
        source = (LIB / "summon.sh").read_text()
        self.assertIn('max_attempts="$(python3 "$CONFIG_PY" get max_implement_attempts)"', source)
        self.assertIn('--max-implement-attempts "$max_attempts"', source)

    def test_failed_summon_rolls_back_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as repo, tempfile.TemporaryDirectory() as state_home:
            subprocess.run(["git", "init", "-q", repo], check=True)
            fake_bin = Path(repo, "fake-bin")
            fake_bin.mkdir()
            fake_tmux = fake_bin / "tmux"
            fake_tmux.write_text("#!/usr/bin/env sh\nexit 1\n", encoding="utf-8")
            fake_tmux.chmod(0o755)
            env = {
                **os.environ,
                "PALANTIR_STATE_HOME": state_home,
                "PATH": f"{fake_bin}:{os.environ['PATH']}",
            }
            proc = subprocess.run(
                ["bash", str(LIB / "summon.sh"), "--no-worktree", "rollback probe"],
                cwd=repo,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(proc.returncode, 0)
            self.assertEqual(list((Path(state_home) / "legions").glob("*/manifest.json")), [])

    def test_coordinator_brief_is_event_driven_and_keeps_publication_gate(self) -> None:
        text = panes.coordinator_brief_text({"id": "l1", "goal": "g"})
        self.assertNotIn("closed", text)
        self.assertIn("explicit human approval", text)
        self.assertIn("Never call `,palantir grant` or `,palantir banish`", text)
        self.assertIn("Never call `,palantir summon`", text)
        self.assertIn("Do not poll", text)
        self.assertIn("tmux send-keys", text)
        self.assertIn("kill or restart", text)
        self.assertIn("remain idle", text)

    def test_inject_when_idle_blocks_on_busy_pane(self) -> None:
        with mock.patch.object(panes, "pane_verdict", return_value="busy"):
            ok = panes.inject_when_idle("s", "w", "text", wait_secs=0)
        self.assertFalse(ok)

    def test_inject_when_idle_sends_literal_then_enter(self) -> None:
        calls = []

        def fake_tmux(*args):
            calls.append(args)
            if args[0] == "list-panes":
                return subprocess.CompletedProcess(args, 0, "%7\n", "")
            return subprocess.CompletedProcess(args, 0, "", "")

        with (
            mock.patch.object(panes, "pane_verdict", return_value="empty"),
            mock.patch.object(composer, "run_tmux", side_effect=fake_tmux),
        ):
            ok = panes.inject_when_idle("s", "w", "hello; rm -rf /", wait_secs=1)
        self.assertTrue(ok)
        self.assertEqual(calls[0][:3], ("list-panes", "-t", "=s:w"))
        self.assertEqual(calls[1][:3], ("send-keys", "-t", "%7"))
        self.assertIn("-l", calls[1])  # literal: tmux never interprets the text
        self.assertEqual(calls[2][-1], "Enter")

    def test_inject_when_idle_requires_two_consecutive_empty_verdicts(self) -> None:
        """A pane that starts rendering between classify and send blocks the inject."""
        calls = []

        def fake_tmux(*args):
            calls.append(args)
            if args[0] == "list-panes":
                return subprocess.CompletedProcess(args, 0, "%7\n", "")
            return subprocess.CompletedProcess(args, 0, "", "")

        with (
            mock.patch.object(panes, "CONFIRM_DELAY_SECS", 0),
            mock.patch.object(panes, "pane_verdict", side_effect=["empty", "busy", "empty", "empty"]) as verdict,
            mock.patch.object(composer, "run_tmux", side_effect=fake_tmux),
        ):
            ok = panes.inject_when_idle("s", "w", "text", wait_secs=5, interval=0.01)
        self.assertTrue(ok)
        self.assertEqual(verdict.call_count, 4)
        sends = [c for c in calls if c[0] == "send-keys"]
        self.assertEqual(len(sends), 2)  # one literal payload + one Enter, after the re-check


class ConfigTests(unittest.TestCase):
    def test_defaults_resolve_to_diverse_roles(self) -> None:
        """The shipped defaults must pass the diversity guard out of the box."""
        table = palantir_config.roles(dict(palantir_config.DEFAULTS))
        resolved = machine.resolve_roles(table)
        for role in ("coordinator", "triage", "diagnose", "investigate", "implement"):
            self.assertEqual(resolved[role]["harness"], "copilot")
            self.assertEqual(resolved[role]["model"], "gpt-5.6-sol")
            self.assertEqual(resolved[role]["family"], "gpt")
        self.assertEqual(resolved["adversarial-review"]["harness"], "copilot")
        self.assertEqual(resolved["adversarial-review"]["model"], "claude-fable-5")
        self.assertEqual(resolved["adversarial-review"]["family"], "claude")

    def test_flat_toml_parsing_and_coercion(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp, "config.toml")
            cfg.write_text(
                "\n".join(
                    [
                        "# comment",
                        'default_harness = "claude"',
                        "watch_interval_secs = 5   # inline comment",
                        'unknown_key = "ignored"',
                        "max_implement_attempts = not-a-number",
                    ]
                )
            )
            resolved = palantir_config.load(cfg)
            self.assertEqual(resolved["default_harness"], "claude")
            self.assertEqual(resolved["watch_interval_secs"], 5)
            self.assertEqual(resolved["max_implement_attempts"], palantir_config.DEFAULTS["max_implement_attempts"])
            self.assertNotIn("unknown_key", resolved)

    def test_missing_config_falls_back_to_defaults(self) -> None:
        resolved = palantir_config.load(Path("/nonexistent/palantir.toml"))
        self.assertEqual(resolved, palantir_config.DEFAULTS)


class ComposerTests(unittest.TestCase):
    def test_prompt_is_idle(self) -> None:
        verdict, _ = composer.classify("some output\n~/repo $ ")
        self.assertEqual(verdict, "empty")

    def test_copilot_prompt_is_idle(self) -> None:
        verdict, _ = composer.classify(" / commands · ? help\n 🐟  ❯")
        self.assertEqual(verdict, "empty")

    def test_copilot_empty_input_box_is_idle(self) -> None:
        pane = (
            "/tmp/worktree  Session: 0 AIC used\n"
            "────────────────────────────────\n"
            "❯ \n"
            "────────────────────────────────\n"
            "/ commands · ? help · → next tab  GPT-5.6 Sol · 1.1M context\n"
        )
        verdict, _ = composer.classify(pane)
        self.assertEqual(verdict, "empty")

    def test_copilot_wrapped_footer_with_empty_input_is_idle(self) -> None:
        pane = (
            "/private/tmp/worktree\n"
            "[branch] Session: 0 AIC used\n"
            "────────────────────────────────\n"
            "❯ \n"
            "────────────────────────────────\n"
            "/ commands · ? help · → next tab\n"
            " GPT-5.6 Sol · 1.1M context\n"
        )
        verdict, _ = composer.classify(pane)
        self.assertEqual(verdict, "empty")

    def test_copilot_wrapped_footer_with_active_input_is_busy(self) -> None:
        pane = (
            "/private/tmp/worktree\n"
            "[branch] Session: 0 AIC used\n"
            "────────────────────────────────\n"
            "❯ Run the tests.\n"
            "────────────────────────────────\n"
            "/ commands · ? help · → next tab\n"
            " GPT-5.6 Sol · 1.1M context\n"
        )
        verdict, _ = composer.classify(pane)
        self.assertEqual(verdict, "busy")

    def test_stale_copilot_footer_does_not_hide_new_pending_output(self) -> None:
        pane = (
            "────────────────────────────────\n"
            "❯ \n"
            "────────────────────────────────\n"
            "/ commands · ? help · → next tab\n"
            " GPT-5.6 Sol · 1.1M context\n"
            "Running the requested command\n"
        )
        verdict, _ = composer.classify(pane)
        self.assertEqual(verdict, "pending")

    def test_copilot_nonempty_input_box_is_busy(self) -> None:
        pane = (
            "/tmp/worktree  Session: 0 AIC used\n"
            "────────────────────────────────\n"
            "❯ Run the tests and fix failures.\n"
            "────────────────────────────────\n"
            "/ commands · ? help · → next tab  GPT-5.6 Sol · 1.1M context\n"
        )
        verdict, _ = composer.classify(pane)
        self.assertEqual(verdict, "busy")

    def test_pi_empty_input_is_idle(self) -> None:
        pane = (
            "────────────────────────────────\n"
            "\n"
            "────────────────────────────────\n"
            "/tmp/worktree\n"
            "0.0%/1.0M (auto)  (openrouter) anthropic/claude-opus-4.8 • xhigh\n"
            "MCP: 0/3 servers\n"
        )
        verdict, _ = composer.classify(pane)
        self.assertEqual(verdict, "empty")

    def test_pi_nonempty_input_is_busy(self) -> None:
        pane = (
            "────────────────────────────────\n"
            "Run the tests and fix failures.\n"
            "────────────────────────────────\n"
            "/tmp/worktree\n"
            "0.0%/1.0M (auto)  (openrouter) anthropic/claude-opus-4.8 • xhigh\n"
            "MCP: 0/3 servers\n"
        )
        verdict, _ = composer.classify(pane)
        self.assertEqual(verdict, "busy")

    def test_pi_empty_input_with_active_work_indicator_is_pending(self) -> None:
        pane = (
            "Elapsed 539.5s\n"
            "⠴ Working...\n"
            "────────────────────────────────\n"
            "\n"
            "────────────────────────────────\n"
            "/tmp/worktree\n"
            "10.3%/1.0M (auto)  (openrouter) anthropic/claude-opus-4.8 • xhigh\n"
            "MCP: 0/3 servers\n"
        )
        verdict, _ = composer.classify(pane)
        self.assertEqual(verdict, "pending")

    def test_copilot_empty_input_with_active_work_indicator_is_pending(self) -> None:
        pane = (
            "/tmp/worktree  Session: 490 AIC used\n"
            "────────────────────────────────\n"
            "❯ \n"
            "────────────────────────────────\n"
            "/ commands · ? help · → next tab\n"
            " ◉ Working · 331 B esc interrupt\n"
            " GPT-5.6 Sol · 1.1M context\n"
        )
        verdict, _ = composer.classify(pane)
        self.assertEqual(verdict, "pending")

    def test_spinner_is_pending(self) -> None:
        verdict, _ = composer.classify("⠋ Thinking")
        self.assertEqual(verdict, "pending")

    def test_content_without_prompt_is_busy(self) -> None:
        verdict, _ = composer.classify("compiling module foo\nlinking bar")
        self.assertEqual(verdict, "busy")

    def test_empty_capture_is_unknown(self) -> None:
        verdict, _ = composer.classify("\n\n")
        self.assertEqual(verdict, "unknown")

    def test_carriage_return_ghost_frames_dropped(self) -> None:
        cleaned = composer.strip_ansi("⠋ Loading\r⠙ Loading\r$ ")
        self.assertEqual(cleaned, "$ ")


class StatuslineTests(unittest.TestCase):
    def test_fragment_counts_by_stage(self) -> None:
        import statusline

        rows = [
            {"stage": "implement"},
            {"stage": "holding"},
            {"stage": "cleared_for_human"},
            {"stage": "banished", "teardown_status": "complete"},
        ]
        with mock.patch.object(legion_state.LegionState, "summaries", return_value=rows):
            self.assertEqual(statusline.fragment(), "P:1 H:1 C:1")
        with mock.patch.object(legion_state.LegionState, "summaries", return_value=[]):
            self.assertEqual(statusline.fragment(), "")

    def test_fragment_does_not_count_unknown_or_legacy_stages_as_active(self) -> None:
        import statusline

        rows = [{"stage": "disbanded"}, {"stage": "corrupt"}, {"stage": "bogus"}]
        with mock.patch.object(legion_state.LegionState, "summaries", return_value=rows):
            self.assertEqual(statusline.fragment(), "E:1")

    def test_fragment_surfaces_orphaned_terminal_legions(self) -> None:
        import statusline

        rows = [
            {"stage": "banished"},
            {"stage": "banished", "teardown_status": "failed"},
            {"stage": "banished", "teardown_status": "complete"},
        ]
        with mock.patch.object(legion_state.LegionState, "summaries", return_value=rows):
            self.assertEqual(statusline.fragment(), "O:2")

    def test_fragment_surfaces_transport_errors_and_unrouted_packets(self) -> None:
        import statusline

        rows = [
            {"stage": "implement", "attention": "transport"},
            {"stage": "banished", "teardown_status": "complete", "attention": "unrouted"},
        ]
        with mock.patch.object(legion_state.LegionState, "summaries", return_value=rows):
            self.assertEqual(statusline.fragment(), "P:1 T:1 U:1")


class DashboardSurfaceTests(unittest.TestCase):
    def test_attach_command_honors_outer_tmux_socket(self) -> None:
        with mock.patch.dict(os.environ, {"OUTER_TMUX_SOCKET": "/tmp/outer.sock"}):
            self.assertEqual(
                dashboard.tmux_switch_client_command("legion-l1"),
                ["tmux", "-S", "/tmp/outer.sock", "switch-client", "-t", "=legion-l1"],
            )

    def test_attach_command_defaults_to_inherited_server(self) -> None:
        """Popup jobs inherit $TMUX; bare tmux targets the owning server."""
        env = {k: v for k, v in os.environ.items() if k != "OUTER_TMUX_SOCKET"}
        with mock.patch.dict(os.environ, env, clear=True):
            self.assertEqual(
                dashboard.tmux_switch_client_command("legion-l1"),
                ["tmux", "switch-client", "-t", "=legion-l1"],
            )

    def test_dashboard_theme_is_ecosystem_frappe(self) -> None:
        self.assertEqual(dashboard.THEME, "catppuccin-frappe")
        self.assertEqual(
            dashboard.STAGE_COLOR_ROLES,
            {"holding": "warning", "cleared_for_human": "success", "banished": "error", "corrupt": "error"},
        )

    def test_stage_glyphs_cover_exactly_the_semantic_stages(self) -> None:
        self.assertEqual(set(dashboard.STAGE_GLYPHS), set(dashboard.STAGE_COLOR_ROLES))
        for glyph in dashboard.STAGE_GLYPHS.values():
            self.assertEqual(len(glyph), 1)
            # Nerd Font private-use glyphs stay single-width in tmux/Textual.
            self.assertGreaterEqual(ord(glyph), 0xE000)
            self.assertLessEqual(ord(glyph), 0xF8FF)

    def test_stage_age_is_compact_and_deterministic(self) -> None:
        self.assertEqual(dashboard.stage_age(1_000_000_000, 3_000_000_000), "2s")
        self.assertEqual(dashboard.stage_age(1_000_000_000, 3_662_000_000_000), "1h01m")

    def test_dashboard_hides_only_successfully_torn_down_history(self) -> None:
        rows = [
            {"id": "active", "stage": "implement"},
            {"id": "closed", "stage": "banished", "teardown_status": "complete"},
            {"id": "orphan", "stage": "banished", "teardown_status": ""},
            {"id": "failed", "stage": "banished", "teardown_status": "failed"},
        ]
        self.assertEqual(
            [row["id"] for row in dashboard.visible_rows(rows, False)],
            ["active", "orphan", "failed"],
        )
        self.assertEqual(dashboard.visible_rows(rows, True), rows)

    def test_destructive_dashboard_actions_are_stage_gated(self) -> None:
        self.assertTrue(dashboard.action_available("holding", "answer"))
        self.assertFalse(dashboard.action_available("implement", "answer"))
        self.assertTrue(dashboard.action_available("cleared_for_human", "grant"))
        self.assertFalse(dashboard.action_available("holding", "grant"))
        self.assertFalse(dashboard.action_available("implement", "banish"))
        self.assertTrue(dashboard.action_available("implement", "send-word"))
        self.assertFalse(dashboard.action_available("banished", "send-word"))

    def test_dashboard_requires_typed_confirmation_for_close_actions(self) -> None:
        source = (LIB / "dashboard.py").read_text()
        self.assertIn('"grant-confirm"', source)
        self.assertIn('"banish-confirm"', source)
        self.assertIn('"force-banish-confirm"', source)
        self.assertNotIn('self._run(self.palantir, "banish", legion_id)\n                self.reload()', source)

    def test_dashboard_puts_vim_navigation_first(self) -> None:
        source = (LIB / "dashboard.py").read_text()
        binding_lines = [line.strip() for line in source.splitlines() if line.strip().startswith("Binding(")]
        self.assertEqual(
            binding_lines[:7],
            [
                'Binding("j,down", "cursor_down", "down", key_display="j/↓"),',
                'Binding("k,up", "cursor_up", "up", key_display="k/↑"),',
                'Binding("ctrl+d,pagedown", "page_down", "page down", key_display="^D/PgDn"),',
                'Binding("ctrl+u,pageup", "page_up", "page up", key_display="^U/PgUp"),',
                'Binding("g", "cursor_top", "top"),',
                'Binding("G", "cursor_bottom", "bottom"),',
                'Binding("l", "attach", "attach"),',
            ],
        )
        self.assertIn('Binding("home", "cursor_top", "", show=False, priority=True)', source)
        self.assertIn('Binding("end", "cursor_bottom", "", show=False, priority=True)', source)
        for action in ("cursor_down", "cursor_up", "page_down", "page_up", "cursor_top", "cursor_bottom"):
            self.assertIn(f"def action_{action}(self)", source)

    def test_dashboard_exposes_summon_and_answer_actions(self) -> None:
        source = (LIB / "dashboard.py").read_text()
        self.assertIn('Binding("s", "summon", "summon")', source)
        self.assertIn('Binding("e", "answer", "answer")', source)
        self.assertIn('Binding("y", "grant", "grant")', source)
        self.assertIn('Binding("w", "send_word", "send word")', source)
        self.assertIn('Binding("b", "banish", "banish")', source)
        self.assertIn('self._run(self.palantir, "summon", text)', source)
        self.assertIn('self._run(self.palantir, "answer", legion_id, text)', source)

    def test_fish_completion_uses_only_lore_heavy_public_actions(self) -> None:
        completion = (REPO / "home/dot_config/fish/completions/readonly_,palantir.fish").read_text()
        for action in (
            "summon",
            "farsee",
            "behold",
            "send-word",
            "answer",
            "grant",
            "banish",
            "keep-watch",
            "trial",
        ):
            self.assertIn(f"-a {action}", completion)
        public_actions = completion.splitlines()[0].split()[3:]
        for legacy in ("muster", "status", "nudge", "approve", "disband", "watch", "verify"):
            self.assertNotIn(legacy, public_actions)


if __name__ == "__main__":
    os.environ.pop("PALANTIR_STATE_HOME", None)
    unittest.main(verbosity=2)
