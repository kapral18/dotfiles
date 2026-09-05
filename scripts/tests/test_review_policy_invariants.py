#!/usr/bin/env python3
"""Focused tests for agent instruction invariants."""

from __future__ import annotations

import json
import re
import sys
import unittest

import _test_support  # noqa: F401  (puts scripts/ on sys.path)
from _test_support import REPO


class TestReviewPolicyInvariants(unittest.TestCase):
    def assert_file_contains(self, relative_path: str, *snippets: str) -> None:
        text = (REPO / relative_path).read_text(encoding="utf-8")
        for snippet in snippets:
            assert snippet in text, f"{relative_path} is missing instruction: {snippet}"

    def assert_file_not_contains(self, relative_path: str, *snippets: str) -> None:
        text = (REPO / relative_path).read_text(encoding="utf-8")
        for snippet in snippets:
            assert snippet not in text, f"{relative_path} should not contain: {snippet}"

    def assert_ordered_steps(self, relative_path: str, *steps: str) -> None:
        # Markdown formatters renumber separated lists; the labels and execution order bind.
        text = (REPO / relative_path).read_text(encoding="utf-8")
        previous = -1
        for step in steps:
            label = re.sub(r"^\d+\.\s+", "", step)
            match = re.search(r"^\d+\. " + re.escape(label) + r"$", text, re.MULTILINE)
            self.assertIsNotNone(match, f"{relative_path} is missing ordered step: {step}")
            self.assertGreater(match.start(), previous, f"{relative_path} has reordered step: {step}")
            previous = match.start()

    def test_deep_review_dedups_restated_worker_descriptions_keeps_controller_validation(self):
        self.assert_file_not_contains(
            "home/exact_dot_agents/exact_skills/exact_k-deep-review/readonly_SKILL.md",
            "is part of the default flow after the blocking PR necessity gate",
            "is part of the PR-mode flow for other-authored or unknown-author PRs",
        )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-deep-review/readonly_SKILL.md",
            "Before accepting, rejecting, or rerunning a live-UI worker result, load and follow this complete result-validation procedure.\nRequired reference: `~/.agents/skills/k-deep-review/references/live-ui-validation.md`.",
        )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-deep-review/exact_references/readonly_live-ui-validation.md",
            "Controller validation: reject and rerun any `k-agent-live-ui-review` result that:",
            "uses the controller cwd or base/main runtime as the PR/head target for an explicit PR/branch review without proving that checkout is on the reviewed PR/head branch/sha",
            "Do not reject or rerun a result that reports a valid Playwriter harness blocker:",
            "`~/.agents/skills/k-review/references/live-ui-review.md`",
        )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-deep-review/readonly_SKILL.md",
            "`~/.agents/skills/k-review/references/pr-necessity-auditor.md`",
        )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-review/exact_references/readonly_pr-necessity-auditor.md",
            "Strictly read-only: never edit files, never run state-changing commands, never post or submit to GitHub.",
        )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-review/exact_references/readonly_live-ui-review.md",
            "### Playwriter comparison",
        )

    def test_deep_review_fresh_eyes_uses_resolved_lane_model(self):
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-deep-review/readonly_SKILL.md",
            "named fresh-eyes profiles and generic fresh-eyes launches both use the resolved lane model",
        )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-deep-review/readonly_SKILL.md",
            "Before route/scope discovery or rebuilding its packet, load and follow this complete phase procedure.\nRequired reference: `~/.agents/skills/k-deep-review/references/route-scope.md`.",
        )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-deep-review/exact_references/readonly_route-scope.md",
            "model_required=<resolved value|inherit|default>",
        )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-review/exact_references/readonly_runtime-harnesses.md",
            "Generic fresh-eyes launches must pass the resolved lane model as the profile-equivalent model",
            "named fresh-eyes profiles carry the same resolver-rendered frontmatter",
            "always pass the resolved concrete lane value rather than letting the runtime pick an implicit default",
        )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-review/exact_references/readonly_fresh-eyes.md",
            "Pi/OMP: launch the `k-agent-fresh-eyes` agent profile",
            "model_required=<resolved lanes value|inherit|default>",
            "model_status=exact",
        )
        self.assert_file_contains(
            "home/dot_pi/agent/exact_agents/k-agent-fresh-eyes.md.tmpl",
            "review-agent-model.partial",
            '"harness" "pi"',
            '"agent" "k-agent-fresh-eyes"',
        )
        self.assert_file_contains(
            "home/dot_omp/private_agent/exact_agents/k-agent-fresh-eyes.md.tmpl",
            "review-agent-model.partial",
            '"harness" "omp"',
            '"agent" "k-agent-fresh-eyes"',
        )
        self.assert_file_not_contains(
            "home/dot_pi/agent/exact_agents/k-agent-fresh-eyes.md.tmpl",
            ".model_tier_map.pi.review.model",
        )
        self.assert_file_not_contains(
            "home/dot_omp/private_agent/exact_agents/k-agent-fresh-eyes.md.tmpl",
            ".model_tier_map.omp.review.model",
        )
        self.assert_file_not_contains(
            "home/exact_dot_agents/exact_skills/exact_k-review/exact_references/readonly_fresh-eyes.md",
            "model_required=n/a",
            "model_status=n/a",
        )

    def test_findings_audit_precedes_final_adversarial_verification(self):
        # The audit narrows the candidate set and the adversarial verifier then refutes only
        # what survived. Reverting to the old parallel/adversarial-first order silently doubles
        # verifier work and lets refuted candidates reach the audit.
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-deep-review/readonly_SKILL.md",
            "5. findings audit, inline or delegated by the findings-audit delegation conditions",
            "6. final adversarial verification (cross-family preferred at equal capability, SOP §3.7) over the audited candidate set",
        )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-deep-review/readonly_SKILL.md",
            "Before selecting or launching reviewer lanes, load and follow this complete phase procedure, including the fresh-eyes trigger and launch barrier.\nRequired reference: `~/.agents/skills/k-deep-review/references/reviewer-roster.md`.",
        )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-deep-review/exact_references/readonly_reviewer-roster.md",
            "Launch one to three sighted lanes by default.",
        )
        self.assert_ordered_steps(
            "home/exact_dot_agents/exact_skills/exact_k-deep-review/readonly_SKILL.md",
            "4. **Run controller findings audit on candidate findings.**",
            "5. **Run final adversarial verification.**",
        )
        for mode_file, ordering in (
            (
                "exact_k-review/exact_references/readonly_local_changes.md",
                "Run the Findings-Set Audit from `judging_pipeline.md` in the controller over the candidate set before adversarial verification.",
            ),
            (
                "exact_k-review/exact_references/readonly_pr_review.md",
                "Before adversarial verification, run the candidate queue through the Findings-Set Audit",
            ),
            (
                "exact_k-review/exact_references/readonly_plan_review.md",
                "before adversarial verification",
            ),
            ("exact_k-light-review/readonly_SKILL.md", "before adversarial work"),
        ):
            self.assert_file_contains(
                f"home/exact_dot_agents/exact_skills/{mode_file}",
                ordering,
            )
        for controller in (
            "home/dot_pi/agent/exact_agents/k-agent-review-controller.md.tmpl",
            "home/dot_omp/private_agent/exact_agents/k-agent-review-controller.md.tmpl",
        ):
            self.assert_file_contains(
                controller,
                "load and follow `~/.agents/skills/k-deep-review/SKILL.md` in full",
                "Follow its required phase references at their owning phase",
            )
            # The audit runs before the verifier, so it cannot consume adversarial verdicts;
            # applying those verdicts belongs to the later reconcile phase.
            self.assert_file_not_contains(
                controller,
                "Findings audit reconciles adversarial and live-UI outputs",
            )

    def test_reviewer_lanes_stay_off_the_controller_context(self):
        # A lane's payload is paid N times per review. Loading the router, shared_rules,
        # pr_common, or a mode file roughly doubles it for instructions a read-only lane is
        # forbidden to act on, so the worker contract must stay self-contained.
        worker = "home/exact_dot_agents/exact_skills/exact_k-review/exact_references/readonly_reviewer-worker.md"
        self.assert_file_contains(
            worker,
            "`~/.agents/skills/k-review/references/judging_core.md`",
            "Do not load `k-review/SKILL.md`, `shared_rules.md`, `pr_common.md`, `lanes.md`, or a mode file.",
            "Do not run repo-wide suites, full builds, or whole-suite test runs.",
        )
        # The controller must actually own the shared work the lanes were told to skip.
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-deep-review/readonly_SKILL.md",
            "Before selecting or launching reviewer lanes, load and follow this complete phase procedure, including the fresh-eyes trigger and launch barrier.\nRequired reference: `~/.agents/skills/k-deep-review/references/reviewer-roster.md`.",
        )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-deep-review/exact_references/readonly_reviewer-roster.md",
            "Run any repo-wide suite, full build, or whole-suite test run **once here**",
        )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-deep-review/readonly_SKILL.md",
            "Lanes deliberately do not load `k-review/SKILL.md`, `shared_rules.md`, `pr_common.md`, `lanes.md`, or a mode file.",
        )
        # Three harnesses can put the router back into a lane through profile frontmatter,
        # each by a different mechanism, so the payload cut has to be asserted per harness.
        # Pi `skills:` injects a name/description/location catalog (pi-subagents
        # src/agents/skills.ts buildSkillInjection) that re-invites the router.
        self.assert_file_not_contains(
            "home/dot_pi/agent/exact_agents/k-agent-reviewer.md.tmpl",
            "skills: k-review",
        )
        # OMP `autoloadSkills` injects the skill body itself. Check the frontmatter block,
        # not the whole file, so the prose explaining the omission does not trip the assert.
        omp_reviewer = REPO / "home/dot_omp/private_agent/exact_agents/k-agent-reviewer.md.tmpl"
        omp_frontmatter = omp_reviewer.read_text(encoding="utf-8").split("---")[1]
        assert "autoloadSkills" not in omp_frontmatter, (
            "OMP reviewer frontmatter must not autoload a skill: it injects the skill body, "
            "and k-review would re-add the router that reviewer-worker.md forbids"
        )
        # Claude 2.1.260 initializes the preload list as e.skills ?? []; omission loads
        # no bodies. The shared worker contract selects the assigned lane's lens.
        claude_reviewer = "home/dot_claude/exact_agents/k-agent-reviewer.md.tmpl"
        self.assert_file_not_contains(claude_reviewer, "skills:", "would load every discovered skill")
        # Every harness lane profile still points at the one shared contract.
        for profile in (
            "home/dot_cursor/exact_agents/readonly_k-agent-review-worker.md.tmpl",
            "home/dot_codex/exact_agents/readonly_k-agent-review-worker.toml.tmpl",
            "home/private_dot_copilot/exact_agents/readonly_k-agent-review-worker.agent.md.tmpl",
            "home/dot_claude/exact_agents/k-agent-reviewer.md.tmpl",
            "home/dot_pi/agent/exact_agents/k-agent-reviewer.md.tmpl",
            "home/dot_omp/private_agent/exact_agents/k-agent-reviewer.md.tmpl",
        ):
            self.assert_file_contains(profile, "k-review/references/reviewer-worker.md")

    def test_pi_omp_controller_dispatch_preserves_leaf_and_root_routes(self):
        for path in (
            "home/dot_pi/agent/exact_agents/k-agent-review-controller.md.tmpl",
            "home/dot_omp/private_agent/exact_agents/k-agent-review-controller.md.tmpl",
        ):
            with self.subTest(profile=path):
                source = (REPO / path).read_text(encoding="utf-8")
                self.assertIn('include "dot_config/exact_tmux/agent_prompts/prefix.txt"', source)
                self.assertIn("A delegated child MUST NOT launch, invoke, or delegate to another agent", source)
                self.assertIn("execute only the task and scope in the parent packet", source)
                self.assertIn("The profile name never grants root authority", source)
                self.assertLess(source.index("## Session boundary"), source.index("## Root dispatch"))
                self.assertIn("Plan/design/document review", source)
                self.assertIn("feedback only", source)
                self.assertIn("Standard review", source)
                self.assertIn("Do not promote standard review to deep review", source)
                self.assertIn("explicitly invoked deep review", source)
                self.assertIn("Before fan-out, do not load or run the full `k-review` router", source)
                self.assertNotIn("autoloadSkills:", source.split("---")[1])
                self.assertNotIn("## Phase 0", source)
                self.assertIn("Native invocation notes", source)
        self.assert_file_contains(
            "home/dot_pi/agent/exact_agents/k-agent-review-controller.md.tmpl",
            'context: "fresh"',
            "concurrency: <lanes>",
            "`:<thinking>`",
            "does not consume a separate `thinking` field",
        )
        self.assert_file_contains(
            "home/dot_omp/private_agent/exact_agents/k-agent-review-controller.md.tmpl",
            "one parallel `task` call",
            "take precedence over the parent session model",
        )

    def test_narrow_auditors_load_only_role_required_skills(self):
        for harness, directory, key in (
            ("claude", "home/dot_claude/exact_agents", "skills"),
            ("omp", "home/dot_omp/private_agent/exact_agents", "autoloadSkills"),
        ):
            for role, required in (
                ("findings-auditor", []),
                ("post-review", []),
                ("live-ui-review", ["k-playwriter"]),
                ("pr-necessity-auditor", ["k-review"]),
            ):
                path = f"{directory}/k-agent-{role}.md.tmpl"
                with self.subTest(harness=harness, role=role):
                    source = (REPO / path).read_text(encoding="utf-8")
                    frontmatter = source.split("---")[1]
                    match = re.search(rf"^{key}:([^\n]*(?:\n  - [^\n]+)*)", frontmatter, re.MULTILINE)
                    actual = re.findall(r"k-[a-z-]+", match.group(1)) if match else []
                    self.assertEqual(actual, required, path)
                    self.assertIn(f"k-review/references/{role}.md", source)
                    self.assertIn('include "dot_config/exact_tmux/agent_prompts/prefix.txt"', source)

    def test_catchall_child_has_no_parent_fanout_exception(self):
        self.assert_file_contains("home/dot_claude/exact_agents/claude.md.tmpl", "Do not spawn additional agents.")
        self.assert_file_not_contains("home/dot_claude/exact_agents/claude.md.tmpl", "unless the parent")

    def test_self_authored_fix_loop_is_bounded_scoped_and_gated_once(self):
        # A measured Cursor session (2026-09-04) turned one review defect into a 2.5-hour
        # feature build: three redesigns, a shared-component API change, six full-suite runs,
        # and a dead session with 11 uncommitted files. The loop is bounded, the fix scope is
        # the diff's own behavior, and the repo-wide gate runs once.
        pipeline = "home/exact_dot_agents/exact_skills/exact_k-review/exact_references/readonly_judging_pipeline.md"
        self.assert_file_contains(
            pipeline,
            "Controller: before proposing/applying review fixes, load `~/.agents/skills/k-review/references/review_fixes.md` for fix scope and the verify-and-fix spine.",
        )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-review/exact_references/readonly_review_fixes.md",
            "**Fix scope:** a fix stays inside the behavior the reviewed diff already changes.",
            "a new user-visible state (loading, error, retry), a new prop or export on a component outside the diff's package",
            "it does not build the feature",
            "runs once, after the last fix and before the report, launched in the background",
            "never block a turn on it and never re-run it per iteration",
            "`k-converge` is the only unbounded loop",
            "append `round: <n> fixed=<files> gates=<result>` to the review spec",
        )
        for owner in (
            pipeline,
            "home/exact_dot_agents/exact_skills/exact_k-review/exact_references/readonly_review_fixes.md",
            "home/exact_dot_agents/exact_skills/exact_k-review/exact_references/readonly_review_post_stage.md",
        ):
            self.assert_file_not_contains(
                owner,
                "Repeat until no new surviving findings or hygiene findings remain",
                "Repeat until the four dimensions return clean",
            )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-review/exact_references/readonly_local_changes.md",
            "Missing error handling, states, or flows are proposals under the Fix scope rule",
        )
        self.assert_file_not_contains(
            "home/exact_dot_agents/exact_skills/exact_k-review/exact_references/readonly_local_changes.md",
            "If something is missing (tests, docs, error handling): add it.",
        )
        # The state harness must be an oracle, not a test-name grep (session records 259, 384).
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-review/exact_references/readonly_judging_core.md",
            "## State-Machine Verification Gate\n\nApply SOP `### 3.6 State-Machine Verification` to reviewed behavior that is stateful, parser-like, branch-heavy, or dependent on ordered conditions.\n\nExamples include parsers, tokenizers, formatters, routing/matching logic, retry/workflow loops, permission matrices, compatibility-sensitive branching, multi-flag control flow.\n\nRequired reference: `judging_state.md` (matching heading).",
        )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-review/exact_references/readonly_judging_state.md",
            "The harness is an executable independent oracle",
            "checks that test names appear in a test file, is not a harness",
            "report `harness=tests` and write no manifest",
        )
        # After compaction the session trusts its own anchored ledger (34 image views, record 71).
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-review/exact_references/readonly_shared_rules.md",
            "`fact: <claim> — <anchor> — <verified_at>`",
            "`media: <file> — <caption> — viewed`",
            "a `fact:` or `media:` line this session wrote with an anchor is trusted",
            "SOP §2.8 skepticism applies to other agents' reports, not to this session's anchored ledger",
        )
        # Ambient exploration needs a recorded trigger; five Slack calls found nothing on a
        # self-authored PR with zero threads.
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-review/exact_references/readonly_pr_common.md",
            "append `ambient: trigger=<condition> evidence=<thread id, claim, or user request>` to the review spec",
            "It never runs under a correctness-only constraint",
        )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-review/readonly_SKILL.md",
            "`k-kibana-labels-propose`, or a CI skill at intake",
        )

    def test_expert_lane_registry_is_the_single_roster_source(self):
        lanes = "home/exact_dot_agents/exact_skills/exact_k-review/exact_references/readonly_lanes.md"
        self.assert_file_contains(
            lanes,
            "### `correctness-regressions`",
            "### `security-authz`",
            "### `deletion-replacement`",
            "### `docs-contract-drift`",
            "~/.agents/skills/k-code-quality-tests/SKILL.md",
            "~/.agents/skills/k-codebase-design/SKILL.md",
        )
        # Every wired lens skill must exist, or the lane silently loads nothing.
        body = (REPO / lanes).read_text(encoding="utf-8")
        wired = set(re.findall(r"~/\.agents/skills/(k-[a-z0-9-]+)/SKILL\.md", body))
        assert wired, "lanes.md wires no lens skills"
        for skill in sorted(wired):
            target = REPO / f"home/exact_dot_agents/exact_skills/exact_{skill}/readonly_SKILL.md"
            assert target.is_file(), f"lanes.md wires a missing lens skill: {skill}"
        # Tiers select from the registry instead of re-listing angles inline.
        for tier in (
            "home/exact_dot_agents/exact_skills/exact_k-deep-review/readonly_SKILL.md",
            "home/exact_dot_agents/exact_skills/exact_k-review/exact_references/readonly_pr_review.md",
            "home/exact_dot_agents/exact_skills/exact_k-review/exact_references/readonly_local_changes.md",
        ):
            self.assert_file_contains(tier, "lanes.md")

    def test_adversarial_verifier_runs_a_bounded_cross_family_miss_sweep(self):
        # The verifier is the only different-family read of the diff. Refutation-only wastes it.
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-review/exact_references/readonly_adversarial-verifier.md",
            "## Miss sweep (bounded, after the verdicts)",
            "Return at most three, marked `new-candidate`",
            "the controller re-audits them before judgment",
        )
        self.assert_file_not_contains(
            "home/exact_dot_agents/exact_skills/exact_k-review/exact_references/readonly_adversarial-verifier.md",
            "Do not generate new findings; the finder lanes own discovery.",
        )
        # Native wrappers must not prohibit the shared contract's bounded sweep.
        profiles = sorted((REPO / "home").glob("**/*adversarial-verifier*.tmpl"))
        self.assertEqual(len(profiles), 5)
        for profile in profiles:
            with self.subTest(profile=profile):
                source = profile.read_text(encoding="utf-8")
                self.assertIn("verdicts plus the bounded miss sweep", source.lower())
                self.assertIn("k-review/references/adversarial-verifier.md", source)
                self.assertNotIn("verdicts only", source.lower())
                self.assertNotIn("or generate new findings", source)
        self.assert_file_contains(
            "home/dot_codex/exact_agents/readonly_k-agent-adversarial-verifier.toml.tmpl",
            "Never edit files, post comments, resolve threads, commit, or push.",
        )
        # Sweep candidates bypass the audit unless each controller re-audits them inline.
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-deep-review/readonly_SKILL.md",
            "new-candidate",
            "Before deciding whether to skip or launch final adversarial verification, load and follow this complete phase procedure, including its miss-sweep audit.\nRequired reference: `~/.agents/skills/k-deep-review/references/adversarial-verification.md`.",
        )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-deep-review/exact_references/readonly_adversarial-verification.md",
            "new-candidate",
            "Findings-Set Audit",
        )
        for controller in (
            "home/dot_pi/agent/exact_agents/k-agent-review-controller.md.tmpl",
            "home/dot_omp/private_agent/exact_agents/k-agent-review-controller.md.tmpl",
        ):
            self.assert_file_contains(
                controller,
                "load and follow `~/.agents/skills/k-deep-review/SKILL.md` in full",
                "Follow its required phase references at their owning phase",
            )

    def test_live_ui_windows_is_manual_only_and_purged_from_automatic_flows(self):
        # The Windows/VirtualBox environment is a standalone manual-only skill now;
        # `/k-deep-review`, `/k-build`, `k-agent-live-ui-review`, and `ui-proof` must carry none of its
        # auto-inference or environment-selection machinery.
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-live-ui-windows/readonly_SKILL.md",
            "disable-model-invocation: true",
            "## Manual only — never automatic",
            "Load this skill only when the user explicitly asks, this turn, for Windows/VirtualBox verification",
            "~/.cache/live-ui-windows/registry.json",
            "start it with `VBoxManage startvm <vm> --type headless`",
            'match the line whose `guest port` equals that debug port, not just the first "Rule" match',
            "Leave the guest OS configuration untouched, including Guest Additions",
        )
        self.assert_file_not_contains(
            "home/exact_dot_agents/exact_skills/exact_k-review/exact_references/readonly_live-ui-runtime.md",
            "Environment selection",
            "windows_additional",
            "windows_only",
            "VBoxManage",
            "Windows",
            "VirtualBox",
        )
        self.assert_file_not_contains(
            "home/exact_dot_agents/exact_skills/exact_k-review/exact_references/readonly_live-ui-review.md",
            "windows verification requirement",
            "environments_checked",
        )
        self.assert_file_not_contains(
            "home/exact_dot_agents/exact_skills/exact_k-ui-capture/exact_references/readonly_proof-mode.md",
            "windows verification requirement",
            "environments_checked",
        )
        self.assert_file_not_contains(
            "home/exact_dot_agents/exact_skills/exact_k-deep-review/readonly_SKILL.md",
            "Resolve the Windows/VirtualBox verification requirement once",
        )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-deep-review/readonly_SKILL.md",
            "Before merging candidates, evaluating applicability, selecting targets/config, or launching live UI, load and follow `~/.agents/skills/k-deep-review/references/live-ui-validation.md` in full.",
        )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-deep-review/exact_references/readonly_live-ui-validation.md",
            "Windows/VirtualBox coverage is out of scope for this flow: `k-agent-live-ui-review` verifies the local browser only.",
            "add the manual `~/.agents/skills/k-live-ui-windows/SKILL.md` skill to this turn's work by hand",
        )
        self.assert_file_not_contains(
            "home/exact_dot_agents/exact_skills/exact_k-build/readonly_SKILL.md",
            "the resolved windows verification requirement",
        )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-build/readonly_SKILL.md",
            "The proof-mode contract verifies the local browser only; when the user explicitly wants Windows/VirtualBox coverage too, add the manual `~/.agents/skills/k-live-ui-windows/SKILL.md` skill",
        )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-elastic-domain/exact_references/readonly_kibana-live-ui.md",
            "## Windows/VirtualBox environment translation",
            "Only applies when the manually-invoked `~/.agents/skills/k-live-ui-windows/SKILL.md` skill is used against a Kibana target.",
            "rewrite `kbn_url`'s hostname to VirtualBox's NAT gateway alias `10.0.2.2`",
            "Leave `es_url` untouched",
            "Add `server.host=0.0.0.0` to `required_kbn_flags`",
        )

    def test_text_tournament_joins_normal_iteration_with_cross_family_authority(self):
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-text-tournament/readonly_SKILL.md",
            "Use before a material prose rewrite with several plausible directions",
            "## Automatic in normal iteration",
            "Run automatically only when the target has multiple materially different",
            "State a short rubric",
            "code, generated artifacts, configuration, secret-bearing content, runtime/system behavior",
            "Generate exactly three surgical candidates",
            "both presentation orders",
            "Apply a cross-family, two-order winner as the next normal edit",
            "continue normal iteration without tournament authority",
            "## Return exactly",
            "`Rubric:`",
        )
        self.assert_file_not_contains(
            "home/exact_dot_agents/exact_skills/exact_k-text-tournament/readonly_SKILL.md",
            "disable-model-invocation",
            "Decision needed:",
        )

    def test_research_separates_finding_verification_and_deepening(self):
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-research/readonly_SKILL.md",
            "## Multi-source claim branch",
        )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-research/readonly_SKILL.md",
            "Before collecting, verifying, deepening, or synthesizing those claims, read and follow `~/.agents/skills/k-research/references/multi-source-claims.md` in full.",
        )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-research/exact_references/readonly_multi-source-claims.md",
            "A finder never verifies its own claim.",
            "primary-source URL",
            "exact supporting quote",
            "Every numeric literal in the claim must occur verbatim in that quote.",
            "Reject the claim, not the entity or source.",
            "Deepening goes last.",
            "Any new claim from deepening returns to candidate collection and independent verification.",
            "Only verified claims may enter `,ai-kb`",
        )
