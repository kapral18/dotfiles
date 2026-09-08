#!/usr/bin/env python3
"""Source-contract regressions for the single final review stage (not runtime certification)."""

from __future__ import annotations

import re
import unittest

import _test_support  # noqa: F401
from _test_support import REPO


class TestReviewPolicyInvariants(unittest.TestCase):
    def test_omp_preserves_async_commands_and_effort_without_background_advisors(self):
        text = self.read("home/dot_omp/private_agent/readonly_config.yml.tmpl")
        for block in (
            "advisor:\n  enabled: false",
            "async:\n  enabled: true",
            "enableEffort: true",
            "maxRecursionDepth: 1",
        ):
            self.assertIn(block, text)
        self.assertNotIn("maxEffort: high", text)
        for profile in (REPO / "home/dot_omp/private_agent/exact_agents").glob("*.tmpl"):
            front = profile.read_text().split("---", 2)[1]
            self.assertIn("blocking: true", front, str(profile))
            self.assertNotIn("spawns:", front, str(profile))
            self.assertNotRegex(front, r"tools:.*\btask\b", str(profile))
        self.assertIn("disabledAgents:\n    - reviewer\n    - security-reviewer", text)

    def read(self, path):
        return (REPO / path).read_text()

    def test_production_worker_returns_artifacts_without_qa(self):
        text = self.read(
            "home/exact_dot_agents/exact_skills/exact_k-build/exact_references/readonly_implement-worker.md"
        )
        for clause in (
            "do not execute acceptance checks",
            "Do not run self-review",
            "Return once:",
            "Produced",
            "do not resume",
            "Never commit, push, publish",
        ):
            self.assertIn(clause, text)

    def test_final_review_uses_evidence_without_reviewing_reviewers(self):
        text = self.read("home/readonly_AGENTS.md")
        for clause in (
            "Final reviewers consume shared evidence",
            "MUST NOT re-run successful checks",
            "do not chain a finder, findings auditor, refuter, and post-review auditor",
            "Final verification failure terminates the attempt with evidence.",
            "A new attempt requires user authorization.",
        ):
            self.assertIn(clause, text)

    def test_former_controller_profiles_are_read_only_leaves(self):
        profiles = [
            p
            for p in (REPO / "home").glob("**/exact_agents/*.tmpl")
            if "deep-review" in p.name or "review-controller" in p.name
        ]
        self.assertGreaterEqual(len(profiles), 5)
        for path in profiles:
            with self.subTest(profile=str(path)):
                text = path.read_text()
                front = text.split("---", 2)[1]
                self.assertIn("leaf-boundary.txt", text)
                self.assertNotIn("  - k-deep-review", front)
                self.assertNotIn("  - k-review", front)
                declared = re.search(r"^tools:\s*(.*)$", front, re.MULTILINE)
                if declared:
                    tools = set(re.findall(r"[\w-]+", declared.group(1).lower()))
                    self.assertFalse(tools & {"task", "agent", "edit", "write"}, str(path))
                self.assertIn("review-agent-model.partial", front)

    def test_pi_workers_default_to_fresh_packet_context_without_ambient_inheritance(self):
        for path in (REPO / "home/dot_pi/agent/exact_agents").glob("*.tmpl"):
            with self.subTest(profile=path.name):
                text = path.read_text()
                for flag in (
                    "inheritProjectContext: false",
                    "inheritGlobalContext: false",
                    "inheritSkills: false",
                    "maxSubagentDepth: 0",
                    "defaultContext: fresh",
                ):
                    self.assertIn(flag, text)

    def test_explicit_pi_role_skills_are_preserved(self):
        expected = {
            "public-sources": ("k-public-sources",),
            "code-searcher": ("k-semantic-code-search",),
            "live-ui-review": ("k-playwriter",),
        }
        for role, skills in expected.items():
            text = self.read(f"home/dot_pi/agent/exact_agents/k-agent-{role}.md.tmpl")
            front = text.split("---", 2)[1]
            for skill in skills:
                self.assertIn(f"skills: {skill}\n", front)

    def test_final_profile_contracts_do_not_require_an_upstream_audit_chain(self):
        profiles = list((REPO / "home").glob("**/exact_agents/*verifier*.tmpl"))
        self.assertTrue(profiles)
        for path in profiles:
            with self.subTest(profile=str(path)):
                text = path.read_text().lower()
                self.assertNotIn("audited candidates", text)
                self.assertNotIn("miss sweep", text)

    def test_review_ownership_is_not_edit_authority(self):
        scope = self.read(
            "home/exact_dot_agents/exact_skills/exact_k-deep-review/exact_references/readonly_route-scope.md"
        )
        self.assertIn("authorship, assignment, or review invocation alone grants no edit permission", scope)
        rules = self.read("home/exact_dot_agents/exact_skills/exact_k-review/exact_references/readonly_shared_rules.md")
        self.assertIn("Review alone is read-only regardless of authorship", rules)
        self.assertIn("Never infer commit/push, reply/resolve, or label authority", rules)
        authorship = self.read(
            "home/exact_dot_agents/exact_skills/exact_k-review/exact_references/readonly_authorship.md"
        )
        self.assertIn("review alone never authorizes working-tree edits", authorship)
        self.assertNotIn("find issues and fix them", authorship)

    def test_blind_clarity_preserves_its_independent_contract(self):
        text = self.read("home/exact_dot_agents/exact_skills/exact_k-review/exact_references/readonly_fresh-eyes.md")
        for boundary in (
            "Never run `gh`",
            "Never read commit messages",
            "never read `manifest.json`, `pr.json`",
            "Do NOT flag correctness, edge cases, architecture, performance, security, or domain concerns",
            "Clarity findings cap at MEDIUM",
            "Do not run checks, re-verify another lane, or resume after returning",
        ):
            self.assertIn(boundary, text)
        self.assertNotIn("judging_pipeline.md", text)

    def test_deep_review_keeps_both_judgment_lenses_without_a_verifier_chain(self):
        text = self.read("home/exact_dot_agents/exact_skills/exact_k-deep-review/readonly_SKILL.md")
        self.assertIn("strong artifact review and adversarial challenge as distinct questions", text)
        self.assertIn("never as reviews of one another", text)
        core = self.read("home/exact_dot_agents/exact_skills/exact_k-review/exact_references/readonly_judging_core.md")
        self.assertIn("do not enumerate mutations for every changed condition", core)
        change = self.read(
            "home/exact_dot_agents/exact_skills/exact_k-review/exact_references/readonly_judging_change.md"
        )
        self.assertIn("Do not start a separate findings-audit pass", change)

    def test_windows_and_tournament_remain_explicit_only(self):
        for name in ("k-live-ui-windows", "k-text-tournament", "k-converge"):
            text = self.read(f"home/exact_dot_agents/exact_skills/exact_{name}/readonly_SKILL.md")
            self.assertIn("disable-model-invocation: true", text)
        for path in (REPO / "home").glob("**/exact_agents/*.tmpl"):
            text = path.read_text()
            front = text.split("---", 2)[1] if text.startswith("---") else text
            self.assertNotIn("k-live-ui-windows", front, str(path))

    def test_snapshot_drift_terminates_without_worker_fallback(self):
        snapshot = self.read(
            "home/exact_dot_agents/exact_skills/exact_k-review/exact_references/readonly_pr_snapshot.md"
        )
        self.assertIn("### Drift (one final freshness check)", snapshot)
        self.assertIn(
            "Do not rebuild the pack, repeat intake, re-anchor findings, or restart review automatically.", snapshot
        )
        self.assertIn("withhold the write and report stale anchors", snapshot)
        pack = self.read("home/exact_dot_agents/exact_skills/exact_k-review/exact_references/readonly_context-pack.md")
        self.assertIn("return `blocked: pack_stale`", pack)
        self.assertIn("return `blocked: pack_missing`", pack)
        self.assertNotIn("fall back to live", pack)

    def test_intake_is_material_question_scoped_and_reuses_evidence(self):
        common = self.read("home/exact_dot_agents/exact_skills/exact_k-review/exact_references/readonly_pr_common.md")
        for clause in (
            "read the complete primary PR body",
            "Do not recursively crawl every reachable or potentially relevant reference.",
            "Stop reference expansion when the named question is answered",
            "do not issue a second per-comment request",
            "run only pending planned checks for the frozen candidate",
        ):
            self.assertIn(clause, common)
        self.assertNotIn("Repeat until the queue is empty", common)

    def test_delivery_does_not_infer_repairs_or_worker_reruns(self):
        delivery = self.read(
            "home/exact_dot_agents/exact_skills/exact_k-review/exact_references/readonly_review_delivery.md"
        )
        self.assertIn("Do not rerun a worker or restart verification automatically.", delivery)
        self.assertIn("Review alone does not authorize edits.", delivery)
        self.assertNotIn("block/rerun", delivery)


if __name__ == "__main__":
    unittest.main()
