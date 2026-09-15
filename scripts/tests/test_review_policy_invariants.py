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
            "Final reviewers use shared evidence and direct artifact access",
            "MUST NOT re-run passing checks for independence",
            "do not chain finder → auditor → refuter → post-auditor over the same work",
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
        self.assertIn("Fix authority follows write scope, not review mode", rules)
        self.assertIn(
            "read-only by its own category regardless of authorship",
            rules,
        )
        self.assertIn("Never infer commit/push, reply/resolve, or label authority", rules)
        authorship = self.read(
            "home/exact_dot_agents/exact_skills/exact_k-review/exact_references/readonly_authorship.md"
        )
        self.assertIn("Authorship is one input to write scope, not the gate itself", authorship)
        self.assertIn(
            "the root's default packet already holds full local write scope",
            authorship,
        )
        self.assertNotIn("review alone never authorizes working-tree edits", authorship)

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
        intake = self.read("home/exact_dot_agents/exact_skills/exact_k-github/readonly_SKILL.md")
        self.assertIn(
            "Load `~/.agents/skills/k-github/SKILL.md` and follow its "
            "GitHub Context Intake + Reference Resolution section.",
            common,
        )
        for clause in (
            "Do not recursively crawl every reachable or potentially relevant reference.",
            "Stop reference expansion when the named question is answered",
            "## GitHub Context Intake + Reference Resolution",
            "Read complete primary discussion before relying on it",
            "Follow a reference only when it can settle a named material question",
            "For selected media, use `~/.agents/skills/k-review/references/pr_snapshot.md` → Media, "
            "inspect the actual file, and retain the manifest evidence.",
            "stop and ask for visuals or better access before making that claim.",
            "Retrieve complete raw artifacts with pagination before relying on them",
            "intake-only use MUST NOT start PR resolution, pending-review handling, mutation, "
            "or unrelated reference workflows.",
            "NEVER treat a branch number alone as the issue identity.",
            "Use for GitHub effects and GitHub issue context/targeting",
        ):
            self.assertIn(clause, intake)
        for clause in (
            "complete primary body, discussion/review threads and replies",
            "do not issue a second per-comment request",
            "run only pending planned checks for the frozen candidate",
            "Do not begin diff analysis until that PR context is complete.",
        ):
            self.assertIn(clause, common)
        self.assertNotIn("Repeat until the queue is empty", common + intake)

    def test_review_router_loads_intake_read_only_without_posting(self):
        router = self.read("home/exact_dot_agents/exact_skills/exact_k-review/readonly_SKILL.md")
        for clause in (
            "Load `~/.agents/skills/k-github/SKILL.md` only for read-only Targeting and "
            "GitHub Context Intake + Reference Resolution required by shared assessment; "
            "NEVER route that intake into posting or mutation.",
            "Do not load `k-git`, `k-compose-pr`, `k-communication`, or a CI skill at intake.",
            "MUST NOT mutate metadata automatically",
            "invoke the `k-github` skill via the Skill tool for the posting step only after draft/verify",
        ):
            self.assertIn(clause, router)
        self.assertNotIn("`k-github` only at the posting step", router)
        self.assertNotIn("Do not load `k-github`", router)

    def test_assessment_skills_keep_classification_and_fallback_contracts(self):
        scsi = self.read("home/exact_dot_agents/exact_skills/exact_k-semantic-code-search/readonly_SKILL.md")
        for clause in (
            "Use for nontrivial code-impact assessment, conceptual code search, "
            "SCSI index selection, or review base context.",
            "discovery=<checked|unavailable|skipped by request>; <reason>",
            "NEVER claim a discovery check that did not run.",
            "If the repo is unindexed, tools are unavailable, or the user opts out, "
            "establish impact from local sources and record the reason.",
            "NEVER run indexed `,sem` queries (`impact`, `context`, `find`, `callers`, `refs`, `grep`, `entities`) as this fallback unless the user explicitly asks",
            "which repositories each server indexes is domain policy owned by the verified domain overlay",
        ):
            self.assertIn(clause, scsi)
        self.assertNotIn("list_indices checked; <reason>", scsi)
        self.assertNotIn("elastic", scsi.lower())
        elastic = self.read("home/exact_dot_agents/exact_skills/exact_k-elastic-domain/readonly_SKILL.md")
        self.assertIn("## Semantic code search scope", elastic)
        self.assertIn("NEVER assume an Elastic index covers a non-Elastic repository.", elastic)
        bugs = self.read("home/exact_dot_agents/exact_skills/exact_k-diagnosing-bugs/readonly_SKILL.md")
        for clause in (
            "Classify the failure as product, test, infrastructure, mixed, or unresolved "
            "from source/reproduction evidence.",
            "does not establish a test-only cause",
            "Return the classification and cause with source/tool anchors",
            "NEVER hide a product defect with a test patch; the original product behavior "
            "remains an acceptance criterion.",
        ):
            self.assertIn(clause, bugs)
        labels = self.read("home/exact_dot_agents/exact_skills/exact_k-kibana-labels-propose/readonly_SKILL.md")
        for clause in (
            "NEVER target a branch merely because it is open or an issue has a matching label.",
            "establish whether the wrong behavior or affected code exists there "
            "and whether the fix applies with its dependencies.",
            "report justified targets and exclusions, or the evidence blocker.",
            "this skill does not authorize a backport or metadata mutation.",
            "This standalone bounded skim MUST NOT weaken the shared intake's "
            "complete-discussion requirements when that intake applies.",
        ):
            self.assertIn(clause, labels)

    def test_delivery_does_not_infer_repairs_or_worker_reruns(self):
        delivery = self.read(
            "home/exact_dot_agents/exact_skills/exact_k-review/exact_references/readonly_review_delivery.md"
        )
        self.assertIn("SOP §3.5", delivery)
        self.assertIn(
            "Fix authority follows write scope per `~/.agents/skills/k-review/references/authorship.md`", delivery
        )
        self.assertNotIn("Review alone does not authorize edits.", delivery)
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

    LAUNCH_PHRASES = (
        "Launch one strong review subagent",
        "Launch one strong final review subagent",
        "Launch distinct strong review and adversarial packets before any final judgment",
    )
    INLINE_BAN = "MUST NOT substitute its own inline review"
    UNAVAILABLE_BLOCKER = "report blocked; do not silently fall back"

    def mandatory_dispatch(self, text):
        """Mandatory isolated-launch predicate: explicit launch plus inline ban plus blocker.
        Source-contract check only; it does not prove model compliance."""
        has_launch = any(phrase in text for phrase in self.LAUNCH_PHRASES)
        return has_launch and self.INLINE_BAN in text and self.UNAVAILABLE_BLOCKER in text

    def dispatch_text_sits_under_root_moves(self, text):
        """True only when every dispatch phrase sits inside the guarded Root moves section."""
        if "## Root moves" not in text:
            return False
        before, rest = text.split("## Root moves", 1)
        section, _, later = rest.partition("\n## ")
        phrases = (*self.LAUNCH_PHRASES, self.INLINE_BAN, self.UNAVAILABLE_BLOCKER)
        if "Only the active root/main session follows this section" not in section:
            return False
        return not any(phrase in before or phrase in later for phrase in phrases)

    def assert_dispatch_text_sits_under_root_moves(self, path):
        self.assertTrue(self.dispatch_text_sits_under_root_moves(self.read(path)), path)

    ROOT_DISPATCH_FILES = (
        "home/exact_dot_agents/exact_skills/exact_k-light-review/readonly_SKILL.md",
        "home/exact_dot_agents/exact_skills/exact_k-review/readonly_SKILL.md",
        "home/exact_dot_agents/exact_skills/exact_k-deep-review/readonly_SKILL.md",
        "home/exact_dot_agents/exact_skills/exact_k-review/exact_references/readonly_local_changes.md",
        "home/exact_dot_agents/exact_skills/exact_k-review/exact_references/readonly_plan_review.md",
        "home/exact_dot_agents/exact_skills/exact_k-review/exact_references/readonly_pr_review.md",
        "home/exact_dot_agents/exact_skills/exact_k-review/exact_references/readonly_pr_fix.md",
        "home/exact_dot_agents/exact_skills/exact_k-deep-review/exact_references/readonly_reviewer-roster.md",
    )

    def test_when_review_tier_is_selected_should_require_isolated_dispatch(self):
        entrypoints = [
            "home/exact_dot_agents/exact_skills/exact_k-light-review/readonly_SKILL.md",
            "home/exact_dot_agents/exact_skills/exact_k-review/readonly_SKILL.md",
            "home/exact_dot_agents/exact_skills/exact_k-deep-review/readonly_SKILL.md",
        ]
        for path in entrypoints:
            with self.subTest(path=path):
                text = self.read(path)
                self.assertIn(
                    "Only the active root/main session follows this section; a delegated leaf skips it",
                    text,
                )
                self.assertTrue(self.mandatory_dispatch(text), path)
        catalog_only = "The contract `~/.agents/skills/k-review/references/reviewer-worker.md` exists."
        self.assertFalse(self.mandatory_dispatch(catalog_only))
        optional_only = (
            "Choose one strong review/refute packet when isolation is useful; small bounded review can remain inline."
        )
        self.assertFalse(self.mandatory_dispatch(optional_only))
        launch_without_ban = f"{self.LAUNCH_PHRASES[0]} when isolation is useful. {self.UNAVAILABLE_BLOCKER}."
        self.assertFalse(self.mandatory_dispatch(launch_without_ban))
        launch_and_ban_without_blocker = f"{self.LAUNCH_PHRASES[0]}. The root {self.INLINE_BAN}."
        self.assertFalse(self.mandatory_dispatch(launch_and_ban_without_blocker))
        ban_and_blocker_without_launch = f"The root {self.INLINE_BAN}; if unavailable, {self.UNAVAILABLE_BLOCKER}."
        self.assertFalse(self.mandatory_dispatch(ban_and_blocker_without_launch))

    def test_when_dispatch_text_exists_should_sit_only_under_root_moves(self):
        for path in self.ROOT_DISPATCH_FILES:
            with self.subTest(path=path):
                self.assert_dispatch_text_sits_under_root_moves(path)
        guard = "Only the active root/main session follows this section; a delegated leaf skips it."
        compliant = (
            f"## Scope\n\nIntro.\n\n## Root moves\n\n{guard}\n{self.LAUNCH_PHRASES[0]}.\n\n## Output\n\nFindings.\n"
        )
        self.assertTrue(self.dispatch_text_sits_under_root_moves(compliant))
        leaked_above = f"{self.LAUNCH_PHRASES[0]} now.\n\n## Root moves\n\n{guard}\n"
        self.assertFalse(self.dispatch_text_sits_under_root_moves(leaked_above))
        leaked_below = f"## Root moves\n\n{guard}\n\n## Mode Selection\n\n{self.LAUNCH_PHRASES[0]} here.\n"
        self.assertFalse(self.dispatch_text_sits_under_root_moves(leaked_below))
        unguarded = f"## Root moves\n\n{self.LAUNCH_PHRASES[0]}.\n"
        self.assertFalse(self.dispatch_text_sits_under_root_moves(unguarded))
        sop = self.read("home/readonly_AGENTS.md")
        self.assertNotIn("light-path judgment only", sop)
        self.assertIn("eligibility routing and terminal synthesis", sop)

    def test_when_review_is_light_or_standard_should_not_allow_discretionary_inline_judgment(self):
        light = self.read("home/exact_dot_agents/exact_skills/exact_k-light-review/readonly_SKILL.md")
        self.assertNotIn("small bounded review can remain inline", light)
        self.assertNotIn("when isolation is useful", light)
        router = self.read("home/exact_dot_agents/exact_skills/exact_k-review/readonly_SKILL.md")
        self.assertNotIn("otherwise isolate substantial context-heavy judgment where it reduces total work", router)
        local = self.read(
            "home/exact_dot_agents/exact_skills/exact_k-review/exact_references/readonly_local_changes.md"
        )
        self.assertNotIn("when isolation is useful", local)
        plan = self.read("home/exact_dot_agents/exact_skills/exact_k-review/exact_references/readonly_plan_review.md")
        self.assertNotIn("when useful", plan)
        fix = self.read("home/exact_dot_agents/exact_skills/exact_k-review/exact_references/readonly_pr_fix.md")
        self.assertNotIn("use strong final judgment where needed", fix)

    def test_when_standard_mode_is_selected_should_reuse_the_required_leaf_packet(self):
        modes = [
            "home/exact_dot_agents/exact_skills/exact_k-review/exact_references/readonly_local_changes.md",
            "home/exact_dot_agents/exact_skills/exact_k-review/exact_references/readonly_plan_review.md",
            "home/exact_dot_agents/exact_skills/exact_k-review/exact_references/readonly_pr_review.md",
            "home/exact_dot_agents/exact_skills/exact_k-review/exact_references/readonly_pr_fix.md",
        ]
        for path in modes:
            with self.subTest(path=path):
                text = self.read(path)
                self.assertTrue(self.mandatory_dispatch(text), path)
                self.assertIn("the same required packet, not additive launches", text)
                self.assertIn("no spawning from a child", text)
        fix = self.read("home/exact_dot_agents/exact_skills/exact_k-review/exact_references/readonly_pr_fix.md")
        self.assertIn("one batch review, not per-thread reviews", fix)

    def test_when_review_is_deep_should_require_distinct_review_and_refute_packets(self):
        entry = self.read("home/exact_dot_agents/exact_skills/exact_k-deep-review/readonly_SKILL.md")
        self.assertIn("`~/.agents/skills/k-review/references/reviewer-worker.md`", entry)
        self.assertIn("`~/.agents/skills/k-review/references/adversarial-verifier.md`", entry)
        self.assertIn("never as reviews of one another", entry)
        roster = self.read(
            "home/exact_dot_agents/exact_skills/exact_k-deep-review/exact_references/readonly_reviewer-roster.md"
        )
        self.assertTrue(self.mandatory_dispatch(roster))
        self.assertIn("using the same packets as the entrypoint", roster)
        # One deep review launched four adversarial packets for one PR (2026-09-14 audit); the bound
        # keeps refutation to one packet per candidate unless a distinct named risk is recorded first.
        self.assertIn(
            "Launch one adversarial packet per frozen candidate; launch another only for a distinct named risk the first packet does not own",
            roster,
        )
        self.assertIn("never this roster or a controller router", roster)

    def test_when_delegation_is_forbidden_or_unavailable_should_distinguish_override_from_blocker(self):
        paths = [
            "home/exact_dot_agents/exact_skills/exact_k-light-review/readonly_SKILL.md",
            "home/exact_dot_agents/exact_skills/exact_k-review/readonly_SKILL.md",
            "home/exact_dot_agents/exact_skills/exact_k-deep-review/readonly_SKILL.md",
            "home/exact_dot_agents/exact_skills/exact_k-review/exact_references/readonly_local_changes.md",
            "home/exact_dot_agents/exact_skills/exact_k-review/exact_references/readonly_plan_review.md",
            "home/exact_dot_agents/exact_skills/exact_k-review/exact_references/readonly_pr_review.md",
            "home/exact_dot_agents/exact_skills/exact_k-review/exact_references/readonly_pr_fix.md",
            "home/exact_dot_agents/exact_skills/exact_k-deep-review/exact_references/readonly_reviewer-roster.md",
        ]
        for path in paths:
            with self.subTest(path=path):
                text = self.read(path)
                self.assertIn("absent an explicit user no-delegation instruction", text)
                self.assertIn("report blocked; do not silently fall back", text)

    ROOT_READ_BOUND_FILES = (
        "home/exact_dot_agents/exact_skills/exact_k-review/readonly_SKILL.md",
        "home/exact_dot_agents/exact_skills/exact_k-light-review/readonly_SKILL.md",
        "home/exact_dot_agents/exact_skills/exact_k-deep-review/readonly_SKILL.md",
    )

    def test_when_root_prepares_a_review_should_be_bound_to_scope_level_reads(self):
        # The root used to "own context collection" while the mode file ordered `git diff`, full-file
        # reads, and blame with no addressee, so the root drifted into worker-depth reading before the
        # mandatory launch. The bound is a hard ban placed under Root moves in every review tier and
        # restated at each reference that previously issued unaddressed read instructions.
        for path in self.ROOT_READ_BOUND_FILES:
            with self.subTest(path=path):
                text = self.read(path)
                self.assertNotIn("context collection", text)
                section = text.split("## Root moves", 1)[1].split("\n## ", 1)[0]
                self.assertIn("MUST NOT read diff hunks, changed-file bodies, callers, or blame output", section)
                self.assertIn("scope-level evidence", section)
        local = self.read(
            "home/exact_dot_agents/exact_skills/exact_k-review/exact_references/readonly_local_changes.md"
        )
        self.assertNotIn("## Investigation (Read-Only, Start Immediately)", local)
        self.assertIn("## Scope Evidence (Root, Read-Only, Start Immediately)", local)
        self.assertIn("## Worker Investigation (Passed In The Packet)", local)
        self.assertIn("record its hash; do not read it.", local)
        self.assertNotIn("- `git diff`\n- `git diff --staged`\n", local)
        for path, phrase in (
            (
                "home/exact_dot_agents/exact_skills/exact_k-review/exact_references/readonly_shared_rules.md",
                "MUST NOT run these source or history reads before the packet returns",
            ),
            (
                "home/exact_dot_agents/exact_skills/exact_k-review/exact_references/readonly_shared_rules.md",
                "never diff hunks or changed-file bodies before the review packet returns",
            ),
            (
                "home/exact_dot_agents/exact_skills/exact_k-review/exact_references/readonly_lanes.md",
                "do not read code bodies to pick lanes or to author the packet",
            ),
            (
                "home/exact_dot_agents/exact_skills/exact_k-review/exact_references/readonly_judging_core.md",
                "MUST NOT read hunks or file bodies itself before that packet returns",
            ),
            (
                "home/exact_dot_agents/exact_skills/exact_k-review/exact_references/readonly_pr_review.md",
                "the root MUST NOT read them before the packet returns",
            ),
            (
                "home/exact_dot_agents/exact_skills/exact_k-review/exact_references/readonly_plan_review.md",
                "MUST NOT read the named source itself before the packet returns",
            ),
        ):
            with self.subTest(path=path, phrase=phrase):
                self.assertIn(phrase, self.read(path))
        for path in self.ROOT_DISPATCH_FILES:
            with self.subTest(path=path, check="no unaddressed root read order"):
                self.assertNotIn("simple targeted reads remain inline", self.read(path))

    def test_when_claim_verifier_gets_a_non_claim_packet_should_block_as_wrong_lane(self):
        # A review packet once ran on this profile and read 430 KB of source (2026-09-14 audit).
        text = self.read(
            "home/exact_dot_agents/exact_skills/exact_k-public-sources/exact_references/readonly_claim-verifier.md"
        )
        self.assertIn("return `blocked: wrong lane` and do nothing else", text)
        self.assertIn("this lane MUST NOT run a code or diff review", text)

    def test_root_forbidden_files_are_not_root_required_elsewhere(self):
        # Reachability both ways (D2): `k-review:24` forbids the root opening the
        # runtime-harness references, so no Root moves section anywhere may require the
        # root to load or open them. Packet-conditional pointers ("as a packet pointer
        # only", "when the scope packet names …") are the sanctioned shape and stay quiet;
        # a bare "Before dispatch, load `runtime-harnesses.md`" fails. Both halves of the
        # split file are covered.
        for name in ("readonly_runtime-harnesses.md", "readonly_runtime-harnesses-pi-omp.md"):
            self.assertTrue(
                (REPO / "home/exact_dot_agents/exact_skills/exact_k-review/exact_references" / name).is_file(),
                f"split harness reference missing: {name}",
            )
        forbidden = {
            "runtime-harnesses.md",
            "runtime-harnesses-pi-omp.md",
            "context-pack.md",
            "execution-controls.md",
        }
        qualifier = re.compile(
            r"pointer only|packet pointer|does not open|MUST NOT|never|packet names|passed in the packet"
        )
        requiring: list[str] = []
        skills_root = REPO / "home/exact_dot_agents/exact_skills"
        for path in sorted(skills_root.rglob("*.md")):
            lines = path.read_text(encoding="utf-8").splitlines()
            in_root_moves = False
            for number, line in enumerate(lines, 1):
                if line.startswith("## "):
                    in_root_moves = line.strip() == "## Root moves"
                    continue
                if not in_root_moves:
                    continue
                if not re.search(r"\b(load|open|read)\b", line, re.IGNORECASE):
                    continue
                # Judge each named file by the clause that names it: a ban on one file must not
                # vouch for a sibling clause that requires another.
                for clause in re.split(r"[;.]\s+|\s+(?:and|then|but)\s+", line):
                    named = {name for name in forbidden if name in clause}
                    if (
                        named
                        and re.search(r"\b(load|open|read)\b", clause, re.IGNORECASE)
                        and not qualifier.search(clause)
                    ):
                        requiring.append(f"{path.relative_to(REPO)}:{number} - {clause.strip()}")
        self.assertEqual([], requiring)
        # The clause split is what makes a mixed line fail: ban on one file, requirement on another.
        mixed = "The root MUST NOT open runtime-harnesses.md; read context-pack.md before dispatch."
        flagged = [
            clause
            for clause in re.split(r"[;.]\s+|\s+(?:and|then|but)\s+", mixed)
            if {name for name in forbidden if name in clause}
            and re.search(r"\b(load|open|read)\b", clause, re.IGNORECASE)
            and not qualifier.search(clause)
        ]
        self.assertEqual(["read context-pack.md before dispatch."], flagged)

    def test_k_review_retry_is_qualified_by_dispatch_outcome(self):
        # X1/D1: the unqualified "A failed launch is retried once with the identical
        # packet" now contradicts SOP §3.7. k-review must carry the qualified taxonomy:
        # rejection-before-run means correct, never retry unchanged, never re-ask;
        # identical retry once only after an executed-then-host/bootstrap/runner failure.
        text = self.read("home/exact_dot_agents/exact_skills/exact_k-review/readonly_SKILL.md")
        self.assertNotIn("A failed launch is retried once with the identical packet", text)
        self.assertIn("correct it, never retry it unchanged, never re-ask permission", text)
        self.assertIn("Retry an identical packet once only when the tool executed", text)


if __name__ == "__main__":
    unittest.main()
