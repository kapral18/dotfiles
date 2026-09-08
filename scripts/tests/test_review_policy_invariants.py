#!/usr/bin/env python3
"""Source-contract regressions for the single final review stage (not runtime certification)."""

from __future__ import annotations

import re
import unittest

import _test_support  # noqa: F401
from _test_support import REPO


def required_skill_references(text):
    """Index explicit load instructions, not catalog mentions or model compliance."""
    return {
        target
        for line in text.splitlines()
        if re.search(r"\b(?:Read|Load|read|load)\b", line)
        for target in re.findall(r"`(~/.agents/skills/[^`]+\.md)`", line)
    }


class TestReviewPolicyInvariants(unittest.TestCase):
    def test_final_duties_are_reachable_from_root_recipes(self):
        routes = {
            "k-light-review/readonly_SKILL.md": (
                "k-review/references/judging_core.md",
                "k-review/references/judging_pipeline.md",
            ),
            "k-build/readonly_SKILL.md": ("k-build/references/criteria-verifier.md",),
            "k-public-sources/readonly_SKILL.md": ("k-public-sources/references/claim-verifier.md",),
            "k-review/readonly_SKILL.md": ("k-review/references/lanes.md",),
            "k-deep-review/readonly_SKILL.md": ("k-deep-review/references/pr-necessity.md",),
            "k-deep-review/exact_references/readonly_reviewer-roster.md": ("k-review/references/lanes.md",),
        }
        for source, targets in routes.items():
            text = self.read(f"home/exact_dot_agents/exact_skills/exact_{source}")
            references = required_skill_references(text)
            for target in targets:
                with self.subTest(source=source, target=target):
                    deployed = f"~/.agents/skills/{target}"
                    self.assertIn(deployed, references)
                    skill, *directories, filename = target.split("/")
                    managed = "/".join([f"exact_{skill}", *(f"exact_{d}" for d in directories), f"readonly_{filename}"])
                    self.assertTrue((REPO / "home/exact_dot_agents/exact_skills" / managed).is_file())
                    # Counterfactual: a surviving file/catalog mention without a load is not a route.
                    catalog_only = f"The contract `{deployed}` exists."
                    self.assertNotIn(deployed, required_skill_references(catalog_only))

    def test_shared_leaf_contracts_reach_every_existing_profile_adapter(self):
        roles = {
            "criteria-verifier": "k-build/references/criteria-verifier.md",
            "claim-verifier": "k-public-sources/references/claim-verifier.md",
            "review-worker": "k-review/references/reviewer-worker.md",
            "change-auditor": "k-review/references/change-auditor.md",
            "live-ui-review": "k-review/references/live-ui-review.md",
        }
        seen_adapters = set()
        for role, contract in roles.items():
            profiles = list((REPO / "home").glob(f"**/exact_agents/*k-agent-{role}.*.tmpl"))
            self.assertTrue(profiles, role)
            for path in profiles:
                with self.subTest(profile=str(path)):
                    text = path.read_text()
                    self.assertIn(f"~/.agents/skills/{contract}", text)
                    self.assertIn("leaf-boundary.txt", text)
                    seen_adapters.add(path.relative_to(REPO / "home").parts[0])
        self.assertEqual(
            seen_adapters,
            {"dot_claude", "dot_codex", "dot_cursor", "dot_pi", "dot_omp", "private_dot_copilot"},
        )

    def test_light_eligibility_remains_a_gate_not_a_small_diff_heuristic(self):
        text = self.read("home/exact_dot_agents/exact_skills/exact_k-light-review/readonly_SKILL.md")
        predicate = text.split("## Light-Eligibility Predicate", 1)[1].split("## Final judgment", 1)[0]
        for condition in (
            "verified self-authorship",
            "Unknown is not eligible",
            "PR context",
            "security/auth/crypto",
            "persisted data",
            "public API",
            "deletion/replacement",
            "stateful/parser/workflow",
            "required base/runtime investigation",
        ):
            self.assertIn(condition, predicate)
        self.assertIn("MUST NOT load another router or start another review", text)

    def test_criteria_judgment_retains_false_green_and_scope_questions(self):
        text = self.read(
            "home/exact_dot_agents/exact_skills/exact_k-build/exact_references/readonly_criteria-verifier.md"
        )
        for duty in ("Criterion truth:", "Reachability:", "Durability:", "Scope accounting:"):
            self.assertIn(duty, text)
        self.assertIn("do not invent extra test runs or mutation passes", text)
        self.assertIn("affected criterion as unknown", text)

    def test_claim_judgment_retains_exact_source_and_numeric_evidence(self):
        text = self.read(
            "home/exact_dot_agents/exact_skills/exact_k-public-sources/exact_references/readonly_claim-verifier.md"
        )
        for duty in (
            "quoted passage occurs in the captured primary source",
            "entails the claim",
            "missing primary-source URL or exact quote",
            "every numeric literal",
            "must occur verbatim in that quote",
            "not unrelated supported claims",
        ):
            self.assertIn(duty, text)

    def test_final_coverage_and_uncertainty_survive_worker_synthesis(self):
        worker = self.read(
            "home/exact_dot_agents/exact_skills/exact_k-review/exact_references/readonly_reviewer-worker.md"
        )
        self.assertIn("Complete every assigned path and criterion", worker)
        self.assertIn("do not stop coverage after the first severe finding", worker)
        self.assertIn("do not expand the search to hunt unrelated risks", worker)
        pipeline = self.read(
            "home/exact_dot_agents/exact_skills/exact_k-review/exact_references/readonly_judging_pipeline.md"
        )
        self.assertIn("material `verification_needed` remains explicit", pipeline)
        self.assertIn("not model votes or a second review", pipeline)
        self.assertIn("explanatory PR narrative is not a refutation", pipeline)

    def test_final_ui_packet_preserves_setup_without_reintroducing_fix_tasks(self):
        worker = self.read(
            "home/exact_dot_agents/exact_skills/exact_k-review/exact_references/readonly_live-ui-review.md"
        )
        self.assertIn("do not edit source or enter fix mode", worker)
        self.assertIn("still permits the selected local/dev setup and data operations", worker)
        self.assertNotIn("Fix mode requires", worker)
        root = self.read(
            "home/exact_dot_agents/exact_skills/exact_k-deep-review/exact_references/readonly_live-ui-validation.md"
        )
        self.assertIn("View each returned screenshot", root)
        self.assertIn("Reuse an already-viewed unchanged image", root)

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
            "A failed required check blocks dependent actions, not authorized diagnosis and repair.",
            "Workers return once; only the root owns recovery, and no worker may start a repair or verification loop.",
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

    def test_snapshot_drift_requires_root_revalidation_without_worker_fallback(self):
        snapshot = self.read(
            "home/exact_dot_agents/exact_skills/exact_k-review/exact_references/readonly_pr_snapshot.md"
        )
        self.assertIn("### Drift (one final freshness check)", snapshot)
        self.assertIn("SOP §3.5", snapshot)
        self.assertNotIn("A new attempt requires user authorization", snapshot)
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
        self.assertIn("SOP §3.5", delivery)
        self.assertIn("Review alone does not authorize edits.", delivery)
        self.assertNotIn("block/rerun", delivery)

    def test_ci_exclusion_precedes_verdict_and_is_not_ci_certification(self):
        common = self.read("home/exact_dot_agents/exact_skills/exact_k-review/exact_references/readonly_pr_common.md")
        self.assertLess(common.index("## CI Coverage Gate"), common.index("## Verdict Gate"))
        for clause in (
            "do not build findings, draft comments, or withhold an approval for that exactly covered class",
            "An observed CI failure in an exactly excluded class is not a failed required acceptance criterion in this review attempt (§3.5).",
            "approval is a review verdict, NEVER CI certification.",
            "It NEVER exempts all bugs or all CI failures.",
        ):
            self.assertIn(clause, common)
        self.assertNotIn("CI failure blocks every approval", common)

    def test_review_publication_reuses_only_existing_sop_authorization(self):
        delivery = self.read(
            "home/exact_dot_agents/exact_skills/exact_k-review/exact_references/readonly_review_delivery.md"
        )
        reviews = self.read("home/exact_dot_agents/exact_skills/exact_k-github/exact_references/readonly_pr-reviews.md")
        self.assertIn("Draft unapproved authored content in chat first.", delivery)
        self.assertIn(
            "existing SOP §3.8 authorization does not already cover the exact target, payload, and effect", delivery
        )
        self.assertIn("Apply the SOP §3.8 authorization and conditions to submit the verdict", delivery)
        self.assertIn("NEVER include `event` in the create-review payload.", reviews)
        self.assertIn("Approval to “approve PR” authorizes the standard short acknowledgement `Looks good.`", reviews)
        self.assertIn("It NEVER authorizes new substantive feedback.", reviews)
        self.assertIn("Unapproved authored content still needs its exact draft and approval under SOP §3.8.", reviews)


if __name__ == "__main__":
    unittest.main()
