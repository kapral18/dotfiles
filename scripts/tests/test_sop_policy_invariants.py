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
            "Composition, review, classification, or human-visible mutation requires complete raw context artifacts",
            "They must not be slices",
            "body[0:N]",
            "re-fetch raw/paginated/JSON output",
        )

    def test_global_sop_keeps_binding_contract_and_skill_routing(self):
        self.assert_file_contains(
            "home/readonly_AGENTS.md",
            "This SOP is binding; do not silently weaken it",
            "Platform/system/developer instructions remain authoritative",
            "When a `Use when` clause matches, load the referenced skill fresh and follow it as written",
            "deviate only when the user explicitly overrides or approves the deviation",
            "This global SOP overrides weaker project-local SOP files",
            "project-local instructions may add constraints but must not weaken this SOP",
            "Continue until the user's goal is complete or a verified blocker/user decision fork remains",
            "Premature stopping (including checkpoint commentary) and instruction/gate violations are operational failures",
        )

    def test_delegated_agents_are_leaf_workers(self):
        for policy, leaf_rule, completion_rule in (
            (
                "home/readonly_AGENTS.md",
                "A delegated child is always a leaf worker, regardless of profile, category, or loaded skill",
                "Complete remaining in-scope work and return its result plus a concise conflict note",
            ),
            (
                "home/dot_config/exact_tmux/agent_prompts/prefix.txt",
                "A delegated child agent is always a leaf worker",
                "Complete the remaining in-scope task",
            ),
        ):
            self.assert_file_contains(
                policy,
                "Only the active root/main session may orchestrate multiple agents or lanes",
                leaf_rule,
                "MUST NOT launch, invoke, or delegate to another agent",
                "MUST NOT create additional review, refutation, audit, or verification lanes",
                "Normal verification inside the assigned task remains required",
                "return the result or a concrete blocker to the parent",
                "ignore that part; do not expand scope",
                completion_rule,
                "Return a concrete blocker only when no in-scope work remains",
            )

        self.assert_file_contains(
            "docs/topics/ai-assistants/subagents.md",
            "Only the active root/main session orchestrates multiple agents or lanes",
            "A controller profile may orchestrate only when it is running as the active root/main session",
            "Delegated children are always leaf workers",
            "completes any remaining leaf-scoped work",
        )
        self.assert_file_contains(
            "docs/topics/ai-assistants/reviews/deep-review-topology.md",
            "the active root/main controller owns every fan-out decision",
            "delegated workers execute one assigned leaf lane",
        )
        self.assert_file_contains(
            "docs/topics/ai-assistants/assets/deep-review-flow.svg",
            "Every delegated worker is a leaf",
            "active root/main controller owns fan-out",
        )
        self.assert_file_contains(
            ".mermaids/S0-concepts.mmd",
            "only the active root/main session orchestrates agents or lanes",
        )
        self.assert_file_contains(
            ".mermaids/03b-agent-skills-hooks.mmd",
            "every delegated child is a leaf worker",
        )

    def test_global_sop_keeps_truth_runtime_and_completion_gates(self):
        self.assert_file_contains(
            "home/readonly_AGENTS.md",
            "Every implementation summary must include: `Compatibility impact: none | removed (requested) | kept existing (requested)`",
            "with no shim, alias, wrapper, or deprecation path",
            "Do not build further reasoning on unverified external behavior",
            "label hypotheses explicitly and do not let them gate downstream steps",
            "Probe locally verifiable assumptions/guesses at the dependent step, not when stated",
            "Resolve material unknowns before proceeding",
            "Keep `/tmp` clones for reuse",
            "Use local code search (`rg`), file reads, and `git log`",
            "Resolve identity before semantics",
            "CLIs: resolve binary path/provenance, then read `--version` and `--help`",
            "Libraries: resolve exact package/version from lockfile, import path, and local docs/source",
            "source config or declaration -> rendered/applied config -> runtime consumer -> minimal safe live probe",
            "Complete investigation, answer, implementation, and verification yourself while required local work remains doable",
            "A summary not verified against full output is a hypothesis, not a fact",
            "Assume unbounded work time and instant development.",
            "Base scope on correctness, evidence, risk, and explicit user constraints",
            "every numeric literal in the claim must occur verbatim in that quote",
            "reject the unverifiable claim, not the source or entity",
        )

    def test_global_sop_keeps_workflow_and_state_machine_gates(self):
        self.assert_file_contains(
            "home/readonly_AGENTS.md",
            "do not load specs broadly",
            "Maintain one active `/tmp/specs/<pwd>/<topic>.txt` topic for the prompt",
            "Keep topics broad/stable; avoid topic explosion",
            "conflicts with target/action/success and lacks a continuation signal",
            "Ask the single most branch-eliminating question while forks remain",
            "Repeat until forks are empty and success criteria testable",
            "For non-trivial/risky work, make plan and per-step verification explicit enough to test",
            "Do not make further speculative changes until alignment is restored",
            "Make success observable; where practical",
            "Bug fixes get reproducing tests",
            "A repo-external `,proof` ledger is a durable receipt, not verification itself",
            "are not ledger triggers by themselves",
            "retroactive creation near the final answer is invalid",
            'Invoke `,proof` only on a concrete trigger above; "the task feels non-trivial" is insufficient',
            "repo-external `,proof` ledger",
            "Test-first framing licenses touching only the code the request covers",
            "### 3.6 State-Machine Verification",
            "require a disposable harness under `/tmp/state-machine-verification/<pwd>/<topic>/<slug>/` before final/merge-ready.",
            "Reuse an existing harness after reading its manifest and confirming it still matches.",
            "Compare implementation against an independent model/table",
            "The harness verifies complexity.",
            "Production state machines need an explicit request.",
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
            "home/dot_config/exact_tmux/agent_prompts/prefix.txt",
            "Treat `,proof` as a durable receipt, not verification itself",
            "only when a durable receipt has a concrete consumer or audit need",
            "not ledger triggers",
            "never start a ledger near the final answer",
            "Otherwise inline anchors are the proof trail",
            "[OUTPUT DISCIPLINE]",
            "Goal: shortest complete essence",
            "Length is a budget, not a vibe",
            "Direct answer ≤80 words",
            "Comparison/audit ≤120",
            "Reach for a density primitive before prose",
            "verdict line, delta table, anchor list",
            "emit a 1-line skeleton",
            "may not restate an item already in an earlier table/list",
            "Brevity outranks structure; structure must earn its space",
            "Borrow STE (ASD-STE100 Simplified Technical English) habits only when they shrink text",
            "§5 owns in-session replies",
            "assume available work time is unbounded and development speed is instant",
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
            "home/dot_config/exact_tmux/agent_prompts/prefix.txt",
            ',probe fail "<summary>"',
            "Passing probes need no record and no separate turn",
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
            "Never `git commit` or `git push` without an explicit request for that action in the current conversation",
            "content approval is not commit authorization",
            "Load `k-git` for the full approvals/push policy before any git side effect",
            "If a human will see the result, draft it, show the exact payload and target, and wait for explicit approval before sending",
            "Human-authored replies/resolves are supervised; no auto-send. Never publish spontaneously, even to bots.",
            "User-invoked `k-pr-fix-loop` explicitly approves scoped PR-fix replies/resolves, PR body edits, and needed PR media uploads in that loop only",
            "Classify authors from platform API evidence, not display-name heuristics",
            "Classify authors from platform API evidence, not display-name heuristics; verify, do not guess",
            "Without a verified domain overlay, classify bots only from platform evidence",
            "does not restrict read-only inspection, local working-tree edits, or `/tmp` work",
            "Before any action/side effect touching paths in a CODEOWNERS repo, verify affected paths belong to the user's team",
            "not guessed from wording",
            "Wording for anyone except the in-session user is centrally owned, not re-derived per surface",
            "a loaded mechanics skill does not own tone",
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
            'Answer questions before acting; treat "can you check/fix/change" as action.',
            "Think from first principles; unverified ideas are hypotheses until probed or sourced.",
            "Choose the narrowest complete path:",
            "include impacted places needed for correctness, push back on unnecessary scope",
            "Default to deeper coverage for non-trivial work",
            "Use the light path only after proving the work is local, reversible, observable, and semantically simple.",
            "Treat any Unknown as a deeper-coverage trigger.",
            "Low-risk proof requires all four conditions:",
            "local = only the requested surface changes;",
            "reversible = no durable or external side effect;",
            "observable = a focused local check can catch the failure;",
            "simple = no ambiguous semantics, branching workflow, hidden consumer, or shared contract.",
            "more source reads, counterexamples, preserved-behavior checks, and relevant skills.",
            "### 1.2 Decision Fallbacks",
            "Questions after a change: explain reasoning and leave it in place unless revision is requested.",
            'keep "this is correct as-is" available as the honest conclusion',
            "unnecessary churn is a defect, not diligence",
            "When uncertain whether to answer or act, answer first, then ask if action is needed.",
            "Handle secrets by reference: keep plaintext credentials out of commits, files, and visible output.",
            "Use a neutral factual tone; skip pandering, apologies, and unnecessary emotional commentary.",
            "Minimize reading load while preserving material facts",
            "Use the shortest complete shape",
            "Add structure only when distinct information scans better",
            "Full STE applies only when the user asks for STE or docs compliance",
            "### 1.1 Time Neutrality",
            "## 5. User Response Shape",
            "Cut restatement, filler, adjectives, and examples before facts",
            "Direct answer or one-shot question: ≤80 words",
            "Comparison or audit: ≤120 words",
            "Multi-part investigation: ≤200 words",
            "Assume unbounded work time and instant development",
            "Base scope on correctness, evidence, risk, and explicit user constraints",
            "Defer only for missing evidence, a user decision fork, or an external blocker",
            "Line 1 answers, decides, or names the next action",
            "Keep every deliverable in the final response after tool work completes",
            "cap at 5",
            "Ask one clarifying question when a remaining fork blocks progress",
            "Code citation format: `startLine:endLine:filepath`",
            "Dotfiles are chezmoi-managed on this machine",
            "consider root causes and indirect effects laterally",
            "Do not stop at the first plausible explanation; verify thoroughly",
            "surface the conflict and ask one direct question",
            '"Concise" means unpadded, not shallow.',
        )
        self.assert_file_not_contains(
            "home/readonly_AGENTS.md",
            "## 6. Decision Fallbacks",
            "### 6.6 Examples",
            "Use examples only when they replace a longer explanation",
        )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-communication/exact_references/readonly_external-replies.md",
            "Choose no reply when it would only restate the thread",
            "Match the surface's register",
            "Use natural wording, or say that no message is worth sending",
        )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-communication/readonly_SKILL.md",
            "Before drafting, apply every rule in `~/.agents/skills/k-communication/references/external-replies.md`.",
            "prefer the shortest structure that still delivers a complete essence",
        )
        self.assert_file_not_contains(
            "home/readonly_AGENTS.md",
            "### 6.5 External Human Replies",
            "Choose no reply when it would only restate the thread",
        )
        self.assert_file_contains(
            "home/readonly_AGENTS.md",
            "### 2.1 Compatibility Gate",
            "Every implementation summary must include: `Compatibility impact: none | removed (requested) | kept existing (requested)`",
        )
        self.assert_file_contains(
            "home/readonly_AGENTS.md",
            "### 3.7 Delegation Categories",
            "Delegation keeps the conclusion in the caller's context, not the file dumps",
            "Classify by work, not caller",
            "A skill that names a category owns that choice",
            "`refute` prefers a different model family at equal capability; a strong same-family refuter beats a weaker cross-family one",
            "Repo-owned custom subagent identifiers MUST use the `k-agent-<role>` namespace.",
            "Harness-native subagent identifiers MUST remain unchanged; do not prefix or alias them.",
            "Centrally mapped per-harness model rows make the category the whole cost decision;\nthe harness resolves",
            "profile, role, tier, or band-gate mechanism",
        )
        self.assert_file_contains(
            "home/readonly_AGENTS.md",
            "Recall first through `k-agent-smol` when prior knowledge could help",
            "Do not run `,ai-kb search`/`,ai-kb get` inline in the parent session",
            "never store guesses or session-only notes",
            "Record worthwhile mid-task decisions, ideas, and unverified constraints with `,agent-memory note",
            "At each substantive turn's end, silently check whether a verified durable/reusable insight was produced",
            "not a checkpoint and not a reason to stop early",
            "No announcement or separate summary",
            "No per-session cap; dedup before writing",
        )

    def test_ai_instructions_keep_semantic_delta_contract_wired(self):
        self.assert_file_contains(
            "home/readonly_AGENTS.md",
            "Before editing, state: old rule -> new rule -> intended differences -> preserved differences -> evidence",
            "Exempt only proven mechanical edits:",
            "formatting, generated metadata from checked source, pure rename with all references updated, or prose/comment text with no behavioral claim",
            "old rule -> new rule -> intended differences -> preserved differences -> evidence",
            "investigate an unknown set, marking `Unknown` only when evidence is genuinely unavailable",
            "preserve behavior outside the semantic delta",
            "Exercise the semantic delta:",
            "at least one intended and one preserved difference when both are locally observable",
            "Name states, transitions, inputs, terminal actions, existing buckets, semantic delta",
        )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-code-quality/readonly_SKILL.md",
            "For edits not proven mechanical-only, carry the SOP semantic delta into the edit",
            "old rule, new rule, intended differences, preserved differences, and evidence for each",
            "If an edit changes what inputs, states, events, persisted data, rendered output, errors, permissions, or generated artifacts mean or produce",
            "When the semantic delta changes one projection of a relationship",
        )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-spec/readonly_SKILL.md",
            "For packets not proven mechanical-only",
            "record SOP semantic delta before criteria",
            "when semantic delta exists, criteria must cover it",
            "one intended-difference and one preserved-difference when both are locally observable",
            "Semantic delta: <none | old rule; new rule; intended differences; preserved differences; evidence>",
        )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-build/readonly_SKILL.md",
            "If the packet is not proven mechanical-only and lacks a semantic delta",
            "Carry the packet's semantic delta into the plan",
            "missing intended difference, or missing preserved difference",
            "The verifier must try to refute the semantic delta, not only the positive criteria",
            "Semantic delta: old rule, new rule, intended differences, preserved differences",
        )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-review/exact_references/readonly_judging_core.md",
            "For diffs not proven mechanical-only, reconstruct semantic delta",
            "Missing/extra/unproven rows are candidates",
            "Compare fix delta with requested delta",
            "Trigger: semantic delta changes how a domain relationship is interpreted",
        )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-review/exact_references/readonly_judging_core.md",
            "## Semantic-Projection & Sibling-Consumer Gate\n\nTrigger: semantic delta changes how a domain relationship is interpreted, projected, stored, rendered, compared, filtered, or serialized.\n\nRequired reference: `judging_change.md` (matching heading).",
        )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-review/exact_references/readonly_judging_change.md",
            "Delta divergence",
        )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-code-quality-tests/readonly_SKILL.md",
            "Before claiming a test covers a changed observable relation",
            "at least one intended difference fails and, when locally observable, at least one preserved difference fails",
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

    def test_global_sop_does_not_carry_skill_routing_triggers(self):
        # Routing triggers live in each skill's `description` frontmatter (which harnesses
        # pass to the model); the model decides when to load. The SOP keeps only fail-closed
        # gates and always-on behavior, never "load skill X when Y" routing. Always-on tool
        # behavior (e.g. ,ai-kb recall/persist) stays, but the skill-load trigger does not.
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
            "If markup, styling, or accessibility semantics change, also load the `~/.agents/skills/k-code-quality-web/SKILL.md` skill.",
            "Use one functional React component per file when writing React",
            "Prefer hooks and composition over class components or inheritance",
        )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-code-quality-tests/readonly_SKILL.md",
            "Use when adding, editing, reviewing, or debugging tests or test plans",
            "Write BDD-style tests when adding tests: `describe('WHEN ...')`, `it('SHOULD ...')`",
            "Bug fix reframe: write a test that reproduces the bug, then make it pass",
        )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-code-quality-web/readonly_SKILL.md",
            "Use for browser-rendered markup, CSS, layout, visual states, accessibility, or focus behavior edits/reviews",
            "## Secondary Skill Escalation",
            "If the concrete web surface is React/JSX/TSX, also load the `~/.agents/skills/k-code-quality-react/SKILL.md` skill.",
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
