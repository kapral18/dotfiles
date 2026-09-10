#!/usr/bin/env python3
"""Tests for SOP, prompt, and agent-instruction policy invariants."""

from __future__ import annotations

import re
import unittest

import _test_support  # noqa: F401  (puts scripts/ on sys.path)
from _test_support import REPO


def _sop_rule_text() -> str:
    """Return the compiled core SOP."""
    return (REPO / "home/readonly_AGENTS.md").read_text(encoding="utf-8")


class TestSopPolicyInvariants(unittest.TestCase):
    """WHEN guarding high-risk SOP and agent-instruction policy."""

    def assert_file_contains(self, relative_path: str, *snippets: str) -> None:
        text = (
            _sop_rule_text()
            if relative_path == "home/readonly_AGENTS.md"
            else (REPO / relative_path).read_text(encoding="utf-8")
        )
        for snippet in snippets:
            assert snippet in text, f"{relative_path} is missing instruction: {snippet}"

    def assert_file_not_contains(self, relative_path: str, *snippets: str) -> None:
        text = (
            _sop_rule_text()
            if relative_path == "home/readonly_AGENTS.md"
            else (REPO / relative_path).read_text(encoding="utf-8")
        )
        for snippet in snippets:
            assert snippet not in text, f"{relative_path} should not contain: {snippet}"

    def test_global_sop_forbids_sliced_context_artifacts(self):
        self.assert_file_contains(
            "home/readonly_AGENTS.md",
            "requires complete raw artifacts, never `body[0:N]`",
            "never `body[0:N]`, `head`, previews, or partial comment lists",
            "body[0:N]",
            "A summary not verified against full output is a hypothesis.",
        )

    def test_global_sop_keeps_binding_contract_and_skill_routing(self):
        self.assert_file_contains(
            "home/readonly_AGENTS.md",
            "This SOP is binding. Do not weaken it silently.",
            "Platform/system/developer instructions stay authoritative.",
            "load that skill file fresh and follow it as written. Memory is not the source.",
            "Deviate only on explicit user override or approval.",
            "project-local instructions may add constraints but must not weaken it.",
            "Continue until the user's goal is complete, §3.5 requires a stop, or a verified blocker/user decision fork remains.",
            "Premature stopping (including checkpoint commentary) and instruction/gate violations are operational failures.",
        )

    def test_delegated_agents_are_leaf_workers(self):
        for policy in ("home/readonly_AGENTS.md", "home/dot_config/exact_tmux/agent_prompts/leaf-boundary.txt"):
            self.assert_file_contains(
                policy,
                "MUST NOT launch, invoke, or delegate to another agent",
                "Research/production workers MUST NOT run verification, review, audit, refutation, or convergence.",
                "A final Verify worker MUST NOT create another lane or repeat a completed check.",
                "Late events MUST NOT overwrite a terminal result or reopen a completed worker.",
            )

    def test_global_sop_keeps_truth_runtime_and_completion_gates(self):
        self.assert_file_contains(
            "home/readonly_AGENTS.md",
            "`Compatibility impact: none | removed (requested) | kept existing (requested)`",
            "Simplify/remove/replace requested",
            "Do not build reasoning on unverified external behavior",
            "5. Probe locally verifiable assumptions/guesses at the dependent step, not when stated.",
            "Resolve material unknowns before proceeding",
            "3. Public source",
            "1. Identity before semantics",
            "source config or declaration -> rendered/applied config -> runtime consumer -> minimal safe live probe",
            "never offer verification as an optional next step.",
            "A summary not verified against full output is a hypothesis.",
            "Do not rerun unchanged checks without new evidence, weaken criteria, expand scope, or polish speculatively.",
            "Base scope on correctness, evidence, risk, and explicit user constraints",
            "7. Anchor synthesis in primary evidence; qualify unsupported claims; do not launch per-claim verifier workflows.",
        )

    def test_global_sop_keeps_workflow_and_state_machine_gates(self):
        self.assert_file_contains(
            "home/readonly_AGENTS.md",
            "do not load specs broadly",
            "Keep topics broad and stable",
            "Order: investigate read-only",
            "stop speculative edits and repeated checks.",
            "Scope → Understand → Produce → Verify → Deliver",
            "Research/production workers MUST NOT run acceptance tests",
            "Run known commands with deterministic tools, not a model turn.",
            "Do not add a production state-machine framework for this.",
            "Compare against an independent model/table",
            "skip checks whose prerequisites failed.",
            "If the candidate changes during Verify, invalidate affected evidence and certify only the revalidated snapshot.",
        )
        self.assert_file_not_contains(
            "home/exact_dot_agents/exact_skills/exact_k-code-quality/readonly_SKILL.md",
            "## State-Machine Verification",
            "Before calling such behavior final or merge-ready",
        )

    def test_proof_access_requires_a_receipt_consumer_or_audit_need(self):
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-proof/readonly_SKILL.md",
            "Use `,proof` only when at least one receipt trigger applies",
            "No other task property is a trigger by itself",
            "Do not create a ledger near the final answer merely to repackage checks that are already sufficient inline",
            "Finalize the receipt",
            'tool_version: ",proof 0.2.0"',
        )
        self.assert_file_contains(
            "home/readonly_AGENTS.md",
            '`<cmd> || ,probe fail "<summary>"`',
            "Use the shortest complete shape",
            "cut words, never facts.",
            "Direct answer or one-shot question: ≤80 words",
            "Comparison or audit: ≤120 words",
            "Prefer a density primitive to prose",
            "verdict line, delta table, anchor list",
            "emit a 1-line skeleton",
            "full STE only when the user asks for STE or docs compliance.",
            "Do not rerun unchanged checks without new evidence, weaken criteria, expand scope, or polish speculatively.",
        )
        # The reinforcement excerpt keeps only the hard budgets and the deliverable rule.
        self.assert_file_contains(
            "home/dot_config/exact_tmux/agent_prompts/prefix.txt",
            "[SOP REINFORCEMENT",
            "Direct answer or one-shot question: ≤80 words",
            "The final message holds every deliverable",
            "Do not rerun unchanged checks without new evidence, weaken criteria, expand scope, or polish speculatively.",
        )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-compose-pr/exact_references/readonly_publication-packet.md",
            "Consume it as completion proof only when `allowed` is true, `finalized_at` is set, and `seal_status` is `ok`",
            "presenting it as proof or finishing it retroactively during PR composition is off limits",
        )
        self.assert_file_not_contains(
            "home/exact_dot_agents/exact_skills/exact_k-proof/readonly_SKILL.md",
            "when verifying runtime/UI/external behavior",
            "when a freeform completion claim depends on multiple evidence sources",
        )
        self.assert_file_not_contains(
            "home/dot_config/exact_tmux/agent_prompts/prefix.txt",
            "runtime/UI/external/security/data/destructive claims, failed attempts, blockers, or multi-evidence changes",
        )

    def test_probe_budget_loop_producer_and_consumer_stay_wired(self):
        # The probe-budget hint only fires if agents actually record probes: the
        # session-injected prefix carries the producer instruction, and the
        # correction detector consumes the ledger. Pin both ends plus the ledger
        # filename contract so one side cannot drift away silently.
        self.assert_file_contains(
            "home/readonly_AGENTS.md",
            ',probe fail "<summary>"',
            '`<cmd> || ,probe fail "<summary>"`',
        )
        # The reinforcement excerpt re-injects the producer line after context growth.
        self.assert_file_contains(
            "home/dot_config/exact_tmux/agent_prompts/prefix.txt",
            ',probe fail "<summary>"',
        )
        # A standalone `,probe pass` turn is a model turn spent on bookkeeping the worklog
        # hook already captures; the producer must not ask for it.
        self.assert_file_not_contains(
            "home/dot_config/exact_tmux/agent_prompts/prefix.txt",
            ',probe pass "<summary>"',
        )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_hooks/correction_detector.py",
            "probe-budget-exhausted",
            ".probe-ledger.jsonl",
        )
        self.assert_file_contains(
            "home/exact_bin/executable_,probe",
            ".probe-ledger.jsonl",
        )
        # `,probe` from a plain shell has no harness session id and records under the
        # `ad-hoc` key, so the reader must keep its ad-hoc fallback, bounded by the
        # failure recency window, or the hint never fires anywhere in practice.
        self.assert_file_contains(
            "home/exact_dot_agents/exact_hooks/correction_detector.py",
            'PROBE_AD_HOC_KEY = "ad-hoc"',
            "PROBE_RECENT_WINDOW_SECONDS",
        )
        # Every per-turn surface that reimplements the correction directive must also
        # carry the probe-budget consumer, or the hint silently fires on some harnesses
        # and not others: pi/omp mirror it in TypeScript, Antigravity rides the
        # premise-nudge PreInvocation drain because it has no user-prompt hook.
        for mirror in (
            "home/dot_pi/agent/exact_extensions/ai-kb-recall.ts",
            "home/dot_omp/private_agent/extensions/ai-kb-recall.ts",
        ):
            self.assert_file_contains(
                mirror,
                "probe-budget-exhausted",
                ".probe-ledger.jsonl",
                'PROBE_AD_HOC_KEY = "ad-hoc"',
                "Probe-budget hint",
            )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_hooks/executable_premise_nudge.py",
            "probe_budget_signal",
            "PROBE_BUDGET_NOTE",
        )

    def test_global_sop_keeps_side_effect_publication_and_git_gates(self):
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-git/readonly_SKILL.md",
            "Never run `git commit` unless the user explicitly requested a commit in the current conversation",
            "Content approval is not commit authorization",
            "When a task would conventionally end with a commit, stop at the working tree and report the change set",
            "A user-invoked `k-pr-fix-loop` approval packet is an explicit commit request for scoped PR-fix commits on the current PR branch",
            "An explicit push request covers committing the changes it describes",
            "Do not push without an explicit push request",
            "Never print configured remote URLs verbatim",
            "Resolve repository and PR identity with platform metadata (`gh repo view`, `gh pr view`) and list remote names with `git remote`",
            "Redaction is not permission to inspect credential-bearing configuration",
        )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-git/readonly_SKILL.md",
            "Before composing a commit message or running commit, amend, or push commands, MUST load and follow `~/.agents/skills/k-git/references/commit-push.md`.",
        )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-git/exact_references/readonly_commit-push.md",
            'Interpret a user request to "push" as explicit approval for `git push --force-with-lease`',
            "A user-invoked `k-pr-fix-loop` approval packet is an explicit force-with-lease push request for the current PR branch only",
            "Prefer explicit remote/branch in the restated command",
            "Never run `git pull`, `git pull --rebase`, `git rebase <remote>/<branch>`, or `git merge <remote>/<branch>` automatically before pushing",
            "If push is rejected for divergence, non-fast-forward, lease failure, or diverged history, stop and ask how to proceed",
            "Do not reconcile branch history unless the user explicitly asks for that exact action",
        )
        self.assert_file_contains(
            "home/readonly_AGENTS.md",
            "NEVER `git commit` or `git push`",
            "content approval is not commit authorization",
            "wait for explicit approval before sending, unless existing authorization",
            "NEVER publish spontaneously, even to bots.",
            "Never stretch a packet to a new target",
            "User-invoked `k-pr-fix-loop` explicitly approves",
            "Classify authors from platform API evidence, never display names",
            "`,codeowners --owner-of <path>`",
            "repo/org evidence, not wording",
            "a mechanics skill does not own tone.",
        )

    def test_global_sop_keeps_quality_communication_and_memory_gates(self):
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-code-quality/readonly_SKILL.md",
            "Preserve all existing behavior outside the explicit scope of the change",
            "Dropping unrelated behavior, even if it looks like cleanup, requires explicit user approval",
            "Use targeted edits, not full-file rewrites",
            "Remove duplication only after proving it is not a point-of-use guard",
            "protects an independently reachable entry point",
            "Every changed line must trace to the request",
            "Before introducing any new file, config, dependency, service, wrapper, generated artifact, or tool-specific metadata",
            "explicitly requested that artifact by name",
            "No abstractions for single-use code",
            "If 200 lines would do as 50, rewrite",
        )
        self.assert_file_contains(
            "home/readonly_AGENTS.md",
            "Skills bind by intent: generic skills own portable mechanics; verified domain overlays own repo/org/product policy.",
            '"can you check/fix/change" is an action request.',
            "Think from first principles; unverified ideas are hypotheses until probed or sourced.",
            "Choose the narrowest complete path:",
            "Choose the narrowest complete path",
            "Default to deeper coverage for non-trivial work",
            "Any Unknown triggers deeper coverage.",
            "Use the light path only after proving all four",
            "### 1.2 Decision Fallbacks",
            "Questions after a change",
            "unnecessary churn is a defect, not diligence.",
            "A question without an active action request needs an answer, not unsolicited changes.",
            "Handle secrets by reference",
            "Use a neutral factual tone.",
            "The user is dyslexic and reads agent output all day.",
            "Use the shortest complete shape",
            "Add structure only when distinct information scans better",
            "full STE only when the user asks for STE or docs compliance.",
            "### 1.1 Time Neutrality",
            "## 5. User Response Shape",
            "cut words, never facts.",
            "Direct answer or one-shot question: ≤80 words",
            "Comparison or audit: ≤120 words",
            "Multi-part investigation: ≤200 words",
            "Minimize total context and model work across the session, including children and advisors.",
            "Base scope on correctness, evidence, risk, and explicit user constraints",
            "No invented permission checkpoints or unbounded retries",
            "Line 1 answers, decides, or names the next action",
            "The final message holds every deliverable (no tool calls after it)",
            "max 5",
            "Code citations: `startLine:endLine:filepath`.",
            "type the comma verbatim",
            "do not stop at the first plausible explanation; verify thoroughly.",
            "surface it and ask one direct question.",
            "Concise means unpadded, not shallow.",
        )
        self.assert_file_not_contains(
            "home/readonly_AGENTS.md",
            "## 6. Decision Fallbacks",
            "### 6.6 Examples",
            "Use examples only when they replace a longer explanation",
        )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-communication/readonly_SKILL.md",
            "Choose no reply when it would only restate the thread",
            "Match the surface's register",
            "Use natural wording, or say that no message is worth sending",
        )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-communication/readonly_SKILL.md",
            "Apply every rule before drafting text another human will read.",
            "use the shortest complete structure",
        )
        self.assert_file_not_contains(
            "home/readonly_AGENTS.md",
            "### 6.5 External Human Replies",
            "Choose no reply when it would only restate the thread",
        )
        self.assert_file_contains(
            "home/readonly_AGENTS.md",
            "### 2.1 Compatibility Gate",
            "`Compatibility impact: none | removed (requested) | kept existing (requested)`",
        )
        self.assert_file_contains(
            "home/readonly_AGENTS.md",
            "Centralize control, not raw context or execution.",
            "Resolve model AND effort from `category_models`",
            "Keep research/orchestration/review/refutation strong",
            "- `mechanical`:",
            "No agent per read, command, check result, or tiny edit.",
            "On compaction or continuation resume from it",
            "Resolve model AND effort from `category_models` in the shared registry.",
            "Repo-owned agent IDs use `k-agent-<role>`",
        )

    def test_ai_instructions_keep_semantic_delta_contract_wired(self):
        self.assert_file_contains(
            "home/readonly_AGENTS.md",
            "Before editing, state the semantic delta",
            "Exempt only proven mechanical edits from stating the delta:",
            "Exempt only proven mechanical edits",
            "AI-facing instruction text steers agent behavior; it is never exempt prose.",
            "old rule -> new rule -> intended differences -> preserved differences -> evidence",
            "mark `Unknown` only when evidence is genuinely unavailable.",
            "preserve behavior outside the semantic delta",
            "Risk-selected mutation experiments must establish control, mutation, and restoration",
            "Do not add a production state-machine framework for this.",
            "plan explicit transition cases",
        )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-code-quality/readonly_SKILL.md",
            "For edits not proven mechanical-only, carry the SOP semantic delta into the edit",
            "old rule, new rule, intended differences, preserved differences, and evidence for each",
            "If an edit changes what inputs, states, events, persisted data, rendered output, errors, permissions, or generated artifacts mean or produce",
            "When the semantic delta changes one projection of a relationship",
            "Non-code artifacts have consumers too:",
        )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-spec/readonly_SKILL.md",
            "Record the semantic delta: old rule, new rule, intended differences, preserved differences, and evidence.",
            "Record the impact map from the SOP §3.1 shared assessment",
            "Criteria cover intended and preserved behavior when both exist",
            "record unrun checks as planned, not passed",
        )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-build/readonly_SKILL.md",
            "Carry old/new rules, intended and preserved differences",
            "the impact map, owned targets",
            "Update every co-edit-set member named in the impact map in the same change",
            "Freeze the integrated candidate",
            "SOP §3.5",
        )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-spec/exact_references/readonly_packet-template.md",
            "Impact map: <none (light-path proven) | affected callers/consumers; invariants; co-edit set",
        )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-build/exact_references/readonly_implement-worker.md",
            "the impact map (affected consumers and co-edit set)",
            "report one outside them as a blocker and do not edit it",
        )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-build/exact_references/readonly_criteria-verifier.md",
            "Look for impact-map consumers or co-edit members left unchanged without evidence that they are unaffected.",
        )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-review/exact_references/readonly_judging_core.md",
            "For diffs not proven mechanical-only, reconstruct semantic delta",
            "Prove mechanical-only with `,sem diff --format json` per `~/.agents/skills/k-sem/SKILL.md`",
            "Missing/extra/unproven rows are candidates",
            "Compare fix delta with requested delta",
            "Trigger: semantic delta changes how a domain relationship is interpreted",
        )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-review/exact_references/readonly_judging_core.md",
            "## Semantic-Projection & Sibling-Consumer Gate\n\nTrigger: semantic delta changes how a domain relationship is interpreted, projected, stored, rendered, compared, filtered, or serialized.\n\nRequired reference: `~/.agents/skills/k-review/references/judging_change.md` (matching heading).",
        )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-review/exact_references/readonly_judging_change.md",
            "Delta divergence",
        )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-code-quality-tests/readonly_SKILL.md",
            "Use an independent oracle and intended/preserved cases.",
            "Do not claim mutation coverage from a green run alone.",
        )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_references/readonly_failure-modes.md",
            "Positive-delta tunnel vision",
            "does not reconstruct the full old-rule -> new-rule semantic delta",
            "shared semantic-delta contract instead of adding per-domain checklists",
        )

    def test_instruction_boundary_skill_replaces_affirmative_phrasing(self):
        self.assertFalse(
            (REPO / "home/exact_dot_agents/exact_skills/exact_k-affirmative-phrasing/readonly_SKILL.md").exists(),
            "old k-affirmative-phrasing skill should be removed",
        )
        self.assert_file_contains(
            "AGENTS.md",
            "Instruction boundaries (mandatory for instruction text)",
            "exact_k-instruction-boundaries/readonly_SKILL.md",
            "default to hard standalone prohibitions for forbidden behavior",
            "add affirmative wording only when it sharpens execution",
        )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-instruction-boundaries/readonly_SKILL.md",
            "name: k-instruction-boundaries",
            "Default to hard boundaries for forbidden behavior",
            "Do not soften a ban into a preference, implication, or positive-only sentence",
            "Preserve standalone prohibitions when the forbidden set is clearer than the allowed set",
            "Add affirmatives only where they reduce ambiguity",
            "Use boundary/action/verification for high-risk gates",
        )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-writing-great-skills/readonly_SKILL.md",
            "load `~/.agents/skills/k-instruction-boundaries/SKILL.md`",
        )
        self.assert_file_contains(
            "docs/topics/ai-assistants/skills/repo-workflow-and-code-intelligence.md",
            "## `k-instruction-boundaries`",
            "hard prohibitions by default",
        )
        self.assert_file_not_contains(
            "AGENTS.md",
            "k-affirmative-phrasing",
            "Affirmative phrasing (mandatory for instruction text)",
        )
        self.assert_file_not_contains(
            "home/exact_dot_agents/exact_skills/exact_k-writing-great-skills/readonly_SKILL.md",
            "k-affirmative-phrasing",
            "phrasing instructions affirmatively instead of as prohibitions",
        )

    def test_global_sop_requires_shared_assessment_before_approach(self):
        self.assert_file_contains(
            "home/readonly_AGENTS.md",
            "During Understand, before settling the assessment or approach for repository diagnosis, "
            "implementation, or review, complete the applicable shared assessment without a second user prompt.",
            "The shared assessment is the four components below: intent intake, impact, cause classification, and release targets;\n"
            "apply each only when its trigger holds.",
            "Impact covers every consumed artifact, not only code:",
            "Impact mechanics, in order: SCSI when the repo is indexed; otherwise local `rg`/symbol lookup",
            "Skip the impact map only for a change proven light-path under §1.",
            "NEVER assume a branch number is the issue identity.",
            "For GitHub issue work, load `~/.agents/skills/k-github/SKILL.md` for Targeting and GitHub Context Intake + Reference Resolution",
            "invariants;\nuse `~/.agents/skills/k-semantic-code-search/SKILL.md` when applicable, "
            "then compare its base context with exact local state.",
            "Route failure work through `~/.agents/skills/k-diagnosing-bugs/SKILL.md` to classify the cause "
            "as product, test, infrastructure, mixed, or unresolved from source/reproduction evidence.",
            "NEVER infer authorization to publish or backport.",
            "Do not force mechanical work through unrelated expensive assessment steps.",
        )

    def test_global_sop_does_not_carry_skill_routing_triggers(self):
        # Routing triggers live in each skill's `description` frontmatter (which harnesses
        # pass to the model); the model decides when to load. The SOP keeps fail-closed
        # gates, always-on behavior, and the §3.1 shared-assessment owner pointers
        # (k-github intake, k-semantic-code-search, k-diagnosing-bugs); it does not carry
        # intent-matched "load skill X when Y" routing for the skills asserted below.
        self.assert_file_not_contains(
            "home/readonly_AGENTS.md",
            "load the applicable code-quality skill",
            "load `~/.agents/skills/k-code-quality",
            "load `~/.agents/skills/k-communication/SKILL.md`",
            "load `~/.agents/skills/k-ai-kb/SKILL.md`",
            "load `~/.agents/skills/k-elastic-domain/SKILL.md`",
            "For human-visible text for anyone other than the in-session user, load",
        )

    def test_ai_kb_skill_owns_quoting_caveat_not_sop(self):
        # Shell-quoting for `,ai-kb remember` arguments is mechanical and command-specific
        # with a loud failure mode (shell error or garbled capsule), not universal or silent.
        # It belongs with the runner-facing CLI contract (the smol operator's reference),
        # not the always-on SOP.
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-ai-kb/exact_references/readonly_cli.md",
            "Markdown backticks trigger shell command substitution unless single-quoted or escaped",
            "an unescaped backtick inside a double-quoted shell argument triggers substitution",
        )
        self.assert_file_not_contains(
            "home/readonly_AGENTS.md",
            "an unescaped backtick inside a double-quoted shell argument triggers substitution",
        )

    def test_code_quality_skills_preserve_extracted_style_guidance(self):
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-code-quality/readonly_SKILL.md",
            "Use when editing, reviewing, or refactoring implementation code or any repository artifact",
            "Match local style, structure, terminology, formatting, and contract strength",
            "Follow `.editorconfig` and existing project conventions",
            "## Secondary Skill Escalation",
            "Do not load secondary skills until read/diff evidence proves the surface is in scope.",
            "When invoked for a broad edit, first identify the concrete changed/read files and choose at most the relevant secondary skill(s).",
            "Do not load React/web/test/design secondaries merely because they might become relevant later.",
            "Load `~/.agents/skills/k-code-quality-react/SKILL.md` when changed/read files are React, JSX, TSX, hooks, or client-side component state.",
            "Load `~/.agents/skills/k-code-quality-tests/SKILL.md` when changed/read files are tests, fixtures, mocks, assertions, or test plans.",
            "Load `~/.agents/skills/k-code-quality-web/SKILL.md` when changed/read files touch browser-rendered HTML, CSS, layout, visual states, accessibility, or focus behavior.",
            "Load `~/.agents/skills/k-codebase-design/SKILL.md` when the task designs a module interface, decides where a seam goes, or aims to make code more testable.",
            "Use precise TypeScript types; `as any` and unnecessary type assertions hide real type errors.",
            "Use `snake_case` for new files unless the project dictates otherwise",
            "Use spaced literals: `{ key: 'value' }`, `[ 1, 2, 3 ]`",
            "Prefer ESM named imports",
            "Replace magic strings with named constants",
            "Prefer composition over inheritance; prefer pure functions over side effects",
            "Keep nesting shallow; use early returns",
            "Keep functions under 50 lines",
            "Prefer `async`/`await` over `.then()` chains",
            "Add JSDoc/TSDoc for complex functions",
            "Run relevant tests/linters when feasible; report results or state why skipped",
        )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-code-quality-react/readonly_SKILL.md",
            "Use when editing, reviewing, or refactoring React/JSX/TSX components, hooks",
            "## Secondary Skill Escalation",
            "If markup, styling, or accessibility semantics change, load `~/.agents/skills/k-code-quality-web/SKILL.md` unless its full text is already loaded for this active invocation.",
            "Use one functional React component per file when writing React",
            "Prefer hooks and composition over class components or inheritance",
        )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-code-quality-tests/readonly_SKILL.md",
            "Use when adding, editing, reviewing, or debugging tests or test plans",
            "Write BDD-style tests when adding tests: `describe('WHEN ...')`, `it('SHOULD ...')`",
            "Write regression cases for the reported bug and preserved behavior",
        )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-code-quality-web/readonly_SKILL.md",
            "Use for browser-rendered markup, CSS, layout, visual states, accessibility, or focus behavior edits/reviews",
            "## Secondary Skill Escalation",
            "If the concrete web surface is React/JSX/TSX, load `~/.agents/skills/k-code-quality-react/SKILL.md` unless its full text is already loaded for this active invocation.",
            "Prefer semantic HTML and existing design-system primitives",
            "Preserve accessible names, roles, focus order, and keyboard reachability",
        )

    def test_secondary_skill_loads_are_evidence_gated(self):

        bad = []
        for path in (REPO / "home/exact_dot_agents/exact_skills").rglob("*SKILL.md"):
            text = path.read_text(encoding="utf-8")
            if "also load `~/.agents/skills/" in text or "also load the `~/.agents/skills/" in text:
                if "## Secondary Skill Escalation" not in text:
                    bad.append(str(path.relative_to(REPO)))
        assert not bad, bad

        code_quality = (REPO / "home/exact_dot_agents/exact_skills/exact_k-code-quality/readonly_SKILL.md").read_text(
            encoding="utf-8"
        )
        first_actions = code_quality.split("## General Code Rules", 1)[0]
        assert "also load the `~/.agents/skills/k-code-quality-react/SKILL.md` skill" not in first_actions
        assert "also load the `~/.agents/skills/k-code-quality-tests/SKILL.md` skill" not in first_actions
        assert "also load the `~/.agents/skills/k-code-quality-web/SKILL.md` skill" not in first_actions
        assert "also load the `~/.agents/skills/k-codebase-design/SKILL.md` skill" not in first_actions

    def test_reinforcement_excerpts_are_verbatim_sop_and_stay_small(self):
        # prefix.txt is re-injected after context growth; leaf-boundary.txt rides in every
        # subagent profile. Both must quote the SOP verbatim (compiler-verified) and stay
        # small, or they recreate the duplicated-context cost they replaced.
        import compile_ai_policy as compiler

        sop = (REPO / "home/readonly_AGENTS.md").read_text(encoding="utf-8")
        self.assertEqual(compiler.excerpt_violations(REPO, sop), [])
        for rel, ceiling in (
            ("home/dot_config/exact_tmux/agent_prompts/prefix.txt", 1200),
            # Architecture-stage allowance includes explicit packet/safety constraints.
            ("home/dot_config/exact_tmux/agent_prompts/leaf-boundary.txt", 2048),
        ):
            size = (REPO / rel).stat().st_size
            self.assertLessEqual(size, ceiling, f"{rel} grew to {size} bytes; keep the excerpt compact")
        self.assert_file_not_contains(
            "home/dot_config/exact_tmux/agent_prompts/prefix.txt",
            "[VERIFICATION DISCIPLINE]",
            "[OUTPUT DISCIPLINE]",
        )

    def test_authorization_and_terminal_rules_have_one_canonical_owner(self):
        self.assert_file_contains(
            "home/readonly_AGENTS.md",
            "assess and stop unless asked to change.",
            "do not require the user to restate it.",
            "A failed required check blocks dependent actions, not authorized diagnosis and repair.",
            "NEVER run an action that depends on the failed criterion.",
            "it survives follow-ups, corrections, compaction, and continuation of the same task.",
            "NEVER infer commit/push/merge authority from it; those effects need their own explicit authorization.",
            "NEVER broaden it to a new target or effect, publish unapproved substantive text, or bypass CI.",
            "wait for explicit approval before sending, unless existing authorization",
            "NEVER publish spontaneously, even to bots.",
            "Never stretch a packet to a new target",
        )
        for policy in (
            "home/exact_dot_agents/exact_skills/exact_k-review/exact_references/readonly_shared_rules.md",
            "home/exact_dot_agents/exact_skills/exact_k-review/exact_references/readonly_review_delivery.md",
            "home/exact_dot_agents/exact_skills/exact_k-review/exact_references/readonly_pr_fix.md",
            "home/exact_dot_agents/exact_skills/exact_k-github/readonly_SKILL.md",
            "home/exact_dot_agents/exact_skills/exact_k-github/exact_references/readonly_pr-reviews.md",
            "home/exact_dot_agents/exact_skills/exact_k-google-workspace/readonly_SKILL.md",
            "home/exact_dot_agents/exact_skills/exact_k-google-workspace/exact_references/readonly_docs-inline-comments.md",
        ):
            self.assert_file_contains(policy, "SOP §3.8")
            self.assert_file_not_contains(
                policy,
                "Authorization persists within its target, scope, and allowed effects until revoked or completed.",
            )
        self.assert_file_contains(
            "home/dot_config/exact_tmux/agent_prompts/prefix.txt",
            "it survives follow-ups, corrections, compaction, and continuation of the same task.",
            "Complete independent authorized actions whose preconditions hold; NEVER run an action that depends on the failed criterion.",
        )

    def test_when_recovery_is_in_scope_should_preserve_evidence_and_stop_boundaries(self):
        # These source contracts guard policy omissions, not future model obedience.
        sop = " ".join(_sop_rule_text().split())
        for required in (
            "a failed check is not a new permission checkpoint.",
            "record in the topic: observed failure, cause evidence, intended correction, affected checks",
            "After repair, freeze the new candidate and rerun failed and affected checks;",
            "keep prior evidence only for unchanged code, environment, and inputs.",
            "Stop affected work only for missing authority, a material user-only decision, a verified external blocker, exhausted §3.4 progress, or an explicit user limit.",
            "Review alone does not authorize edits; report out-of-scope repairs as findings.",
            "When repeated attempts reproduce the same failure with no new evidence or progress, stop speculative edits and repeated checks.",
            "Resume scoped production only when new evidence supports a concrete correction; keep the failure history.",
            "Workers return once; only the root owns recovery, and no worker may start a repair or verification loop.",
        ):
            with self.subTest(boundary=required):
                self.assertIn(required, sop)
        for obsolete in (
            "A new attempt requires user authorization.",
            "Do not automatically repair, restart Produce",
            "When uncertain whether to answer or act, answer first, then ask if action is needed.",
        ):
            self.assertNotIn(obsolete, sop)
