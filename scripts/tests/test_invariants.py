#!/usr/bin/env python3
"""Tests for repository instruction and hook invariants."""

from __future__ import annotations

import unittest

import _test_support  # noqa: F401  (puts scripts/ on sys.path)
from _test_support import REPO


class TestAgentInstructionInvariants(unittest.TestCase):
    """WHEN guarding high-risk agent workflow instructions."""

    def assert_file_contains(self, relative_path: str, *snippets: str) -> None:
        text = (REPO / relative_path).read_text(encoding="utf-8")
        for snippet in snippets:
            assert snippet in text, f"{relative_path} is missing instruction: {snippet}"

    def assert_file_not_contains(self, relative_path: str, *snippets: str) -> None:
        text = (REPO / relative_path).read_text(encoding="utf-8")
        for snippet in snippets:
            assert snippet not in text, f"{relative_path} should not contain: {snippet}"

    def test_global_sop_forbids_sliced_context_artifacts(self):
        self.assert_file_contains(
            "home/readonly_AGENTS.md",
            "Context-bearing artifacts",
            "must be complete raw artifacts",
            "body[0:N]",
            "re-fetch raw/paginated/JSON output",
        )

    def test_global_sop_keeps_binding_contract_and_skill_routing(self):
        self.assert_file_contains(
            "home/readonly_AGENTS.md",
            "binding operational contract",
            "Platform/system/developer instructions remain authoritative",
            "When a `Use when` clause matches, load the referenced skill file and follow it",
            "Do not deviate from specified procedures without explicit user approval",
            "This global SOP overrides project-local or repo-local SOP files when they conflict",
            "Project-local instructions may add repo-specific constraints but must not weaken this SOP",
            "continue working until the user's goal is complete",
            "Any premature stopping, including checkpoint commentary, is an operational failure",
        )

    def test_global_sop_keeps_truth_runtime_and_completion_gates(self):
        self.assert_file_contains(
            "home/readonly_AGENTS.md",
            "Every implementation summary must include: `Compatibility impact: none | removed (requested) | kept existing (requested)`",
            "with no shim, alias, wrapper, or deprecation path",
            "Do not build further reasoning on unverified external behavior",
            "Label hypotheses explicitly and do not let them gate downstream steps",
            "Any locally verifiable assumption or guess must be verified via probes",
            "Resolve material unknowns before proceeding",
            "keep `/tmp` clones for reuse",
            "use local code search (`rg`), file reads, and `git log`",
            "Resolve identity before semantics",
            "For CLIs, resolve the binary path and provenance",
            "For libraries, resolve exact package/version from the lockfile",
            "source config or declaration -> rendered/applied config -> runtime consumer -> minimal safe live probe",
            "Do not stop at a partial investigation, partial answer, or partial implementation",
            "A summary not verified against full output is a hypothesis, not a fact",
            "Do not use human time or perceived effort as a reason to skip verification, simplification, or a locally available probe.",
        )

    def test_global_sop_keeps_workflow_and_state_machine_gates(self):
        self.assert_file_contains(
            "home/readonly_AGENTS.md",
            "do not load specs broadly",
            "Select exactly one topic",
            "Keep topics broad/stable, avoid topic explosion",
            "conflicts with its target, action, or success and lacks a continuation signal",
            "ask the single most branch-eliminating question",
            "repeat until forks are empty and success criteria are testable",
            "For non-trivial or risky work, make the plan and per-step verification explicit enough to test",
            "Do not make further speculative changes until alignment is restored",
            "Reframe imperative tasks to verifiable goals when practical",
            "Bug fix reframe: write a test that reproduces the bug, then make it pass",
            "A repo-external `,proof` ledger is required before a freeform completion claim only when a hard trigger applies",
            "do not invoke `,proof` merely because the task feels",
            "repo-external `,proof` ledger",
            "Test-first framing does not license touching code outside the request",
            "Before calling such behavior final or merge-ready",
            "Reuse an existing harness only after reading its manifest",
            "Compare implementation behavior against an independent model/table",
            "this verifies complexity, not a reason to add production state machines",
        )

    def test_proof_access_is_explicit_and_implicit(self):
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_proof/readonly_SKILL.md",
            "Use when the user explicitly asks how do you know/prove it/receipt",
            "when a freeform completion claim depends on multiple evidence sources",
            "Start a ledger only after a hard trigger fires",
        )
        self.assert_file_contains(
            "home/dot_config/exact_tmux/agent_prompts/prefix.txt",
            "hard-triggered non-review/non-build freeform completion claims",
            "load the proof skill and use a repo-external `,proof` ledger",
            "explicit proof/receipt requests",
            "Otherwise inline anchors are the proof trail",
        )

    def test_global_sop_keeps_side_effect_publication_and_git_gates(self):
        self.assert_file_contains(
            "home/readonly_AGENTS.md",
            "never run `git pull`, `git pull --rebase`, `git rebase <remote>/<branch>`, or `git merge <remote>/<branch>` automatically before pushing",
            "If a human will see the result, draft it, show the exact payload and target, and wait for explicit approval before sending",
            "Never publish spontaneously, even to bots",
            "Classify author type from platform API evidence, not display-name heuristics",
            "Verify author type from platform evidence; do not guess",
            "Without a verified domain overlay, classify bots only from platform evidence",
            "does not restrict read-only inspection, local working-tree edits, or `/tmp` work",
            "Before any action or side effect that touches file paths in a repo with a CODEOWNERS file",
            "not guessed from wording",
            "Wording of human-visible text for anyone other than the in-session user is owned centrally, not re-derived per surface",
            "a loaded mechanics skill does not own tone",
        )

    def test_global_sop_keeps_quality_communication_and_memory_gates(self):
        self.assert_file_contains(
            "home/readonly_AGENTS.md",
            "Do not commit, reveal, or write secrets or plaintext credentials.",
            "All existing behavior outside the explicit scope of the change MUST be preserved",
            "Dropping unrelated behavior, even if it looks like cleanup, requires explicit user approval",
            "Use targeted edits, not full-file rewrites",
            "Remove duplication only after proving it is not a point-of-use guard",
            "protects an independently reachable entry point",
            "Every changed line must trace to the request",
            "Before introducing any new file, config, dependency, service, wrapper, generated artifact, or tool-specific metadata",
            "explicitly requested that artifact by name",
            "No abstractions for single-use code",
            "If 200 lines would do as 50, rewrite",
            "Pre-send self-check",
            "first sentence carries the answer, not narration",
            "last sentence adds new information, not recap",
            "Strip filler, hedging, narrative padding",
            "Anchor with evidence; do not paraphrase the verification chain in prose",
            "choose no reply if the message would only restate the thread",
            "Match the user's/surface's register",
            "Use natural wording or say that no message is worth sending",
            "Also use that shape when the user asked for a trace/comparison/audit",
            "Ask exactly one clarifying question per message and wait for the answer before asking the next",
            "Use code citation format (`startLine:endLine:filepath`) for existing code",
            "Concise result summaries inside the response are required when they carry evidence, outcomes, or next-step constraints",
            "When prior knowledge could help (starting non-trivial work, or hitting a problem the setup likely saw before)",
            "not a checkpoint and not a reason to stop early",
            "no announcement, no separate summary",
            "Think laterally about root causes and indirect effects",
            "Do not stop at the first plausible explanation; verify thoroughly",
            '"Concise" is the opposite of "padded," not the opposite of "thorough."',
            "unnecessary churn is a defect, not diligence",
        )

    def test_global_sop_does_not_carry_skill_routing_triggers(self):
        # Routing triggers live in each skill's `description` frontmatter (which harnesses
        # pass to the model); the model decides when to load. The SOP keeps only fail-closed
        # gates and always-on behavior, never "load skill X when Y" routing. Always-on tool
        # behavior (e.g. ,ai-kb recall/persist) stays, but the skill-load trigger does not.
        self.assert_file_not_contains(
            "home/readonly_AGENTS.md",
            "load the applicable code-quality skill",
            "load `~/.agents/skills/code-quality",
            "load `~/.agents/skills/communication/SKILL.md`",
            "load `~/.agents/skills/ai-kb/SKILL.md`",
            "load `~/.agents/skills/elastic-domain/SKILL.md`",
            "For human-visible text for anyone other than the in-session user, load",
        )

    def test_ai_kb_skill_owns_quoting_caveat_not_sop(self):
        # Shell-quoting for `,ai-kb remember` arguments is mechanical and command-specific
        # with a loud failure mode (shell error or garbled capsule), not universal or silent.
        # It belongs in the skill, not the always-on SOP.
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_ai-kb/readonly_SKILL.md",
            "Markdown backticks trigger shell command substitution unless single-quoted or escaped",
            "Never place unescaped backticks inside a double-quoted shell argument",
        )
        self.assert_file_not_contains(
            "home/readonly_AGENTS.md",
            "Never place unescaped backticks inside a double-quoted shell argument",
        )

    def test_code_quality_skills_preserve_extracted_style_guidance(self):
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_code-quality/readonly_SKILL.md",
            "Use when editing, reviewing, or refactoring implementation code in any language",
            "Match local style, structure, terminology, formatting, and contract strength",
            "Follow `.editorconfig` and existing project conventions",
            "## Secondary Skill Escalation",
            "Do not load secondary skills until read/diff evidence proves the surface is in scope.",
            "When invoked for a broad edit, first identify the concrete changed/read files and choose at most the relevant secondary skill(s).",
            "Do not load React/web/test/design secondaries merely because they might become relevant later.",
            "Load `~/.agents/skills/code-quality-react/SKILL.md` when changed/read files are React, JSX, TSX, hooks, or client-side component state.",
            "Load `~/.agents/skills/code-quality-tests/SKILL.md` when changed/read files are tests, fixtures, mocks, assertions, or test plans.",
            "Load `~/.agents/skills/code-quality-web/SKILL.md` when changed/read files touch browser-rendered HTML, CSS, layout, visual states, accessibility, or focus behavior.",
            "Load `~/.agents/skills/codebase-design/SKILL.md` when the task designs a module interface, decides where a seam goes, or aims to make code more testable.",
            "Avoid TypeScript `as any` and unnecessary type assertions",
            "Use `snake_case` for new files unless the project dictates otherwise",
            "Use spaced literals: `{ key: 'value' }`, `[ 1, 2, 3 ]`",
            "Prefer ESM named imports",
            "Replace magic strings with named constants",
            "Prefer composition over inheritance; prefer pure functions over side effects",
            "Avoid deep nesting; use early returns",
            "Keep functions under 50 lines",
            "Prefer `async`/`await` over `.then()` chains",
            "Add JSDoc/TSDoc for complex functions",
            "Run relevant tests/linters when feasible; report results or state why skipped",
        )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_code-quality-react/readonly_SKILL.md",
            "Use when editing, reviewing, or refactoring React/JSX/TSX components, hooks",
            "## Secondary Skill Escalation",
            "If markup, styling, or accessibility semantics change, also load the `~/.agents/skills/code-quality-web/SKILL.md` skill.",
            "Use one functional React component per file when writing React",
            "Prefer hooks and composition over class components or inheritance",
        )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_code-quality-tests/readonly_SKILL.md",
            "Use when adding, editing, reviewing, or debugging tests or test plans",
            "Write BDD-style tests when adding tests: `describe('WHEN ...')`, `it('SHOULD ...')`",
            "Bug fix reframe: write a test that reproduces the bug, then make it pass",
        )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_code-quality-web/readonly_SKILL.md",
            "Use when editing, reviewing, or refactoring browser-rendered markup, styling, or presentation",
            "## Secondary Skill Escalation",
            "If the concrete web surface is React/JSX/TSX, also load the `~/.agents/skills/code-quality-react/SKILL.md` skill.",
            "Prefer semantic HTML and existing design-system primitives",
            "Preserve accessible names, roles, focus order, and keyboard reachability",
        )

    def test_secondary_skill_loads_are_evidence_gated(self):
        from pathlib import Path

        bad = []
        for path in (REPO / "home/exact_dot_agents/exact_skills").rglob("*SKILL.md"):
            text = path.read_text(encoding="utf-8")
            if "also load `~/.agents/skills/" in text or "also load the `~/.agents/skills/" in text:
                if "## Secondary Skill Escalation" not in text:
                    bad.append(str(path.relative_to(REPO)))
        assert not bad, bad

        code_quality = (REPO / "home/exact_dot_agents/exact_skills/exact_code-quality/readonly_SKILL.md").read_text(
            encoding="utf-8"
        )
        first_actions = code_quality.split("## General Code Rules", 1)[0]
        assert "also load the `~/.agents/skills/code-quality-react/SKILL.md` skill" not in first_actions
        assert "also load the `~/.agents/skills/code-quality-tests/SKILL.md` skill" not in first_actions
        assert "also load the `~/.agents/skills/code-quality-web/SKILL.md` skill" not in first_actions
        assert "also load the `~/.agents/skills/codebase-design/SKILL.md` skill" not in first_actions

    def test_github_pr_publication_requires_preflight_and_readback_comparison(self):
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_github/readonly_SKILL.md",
            "PR creation is a composition action; it is not exempt.",
            "show a PR publication preflight ledger",
            'Approval to "create a PR" authorizes the GitHub side effect, but not invented human-visible content.',
            "Compare each field against the approved preflight ledger",
        )

    def test_issue_publication_requires_type_packet(self):
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_compose-issue/readonly_SKILL.md",
            "issue title/body or issue publication packet",
            "issue publication packet",
            "`issue_type`: exact GitHub issue type",
            "labels do not satisfy it",
            "pick from the repo's actual issue types",
            "Return the issue title/body draft and the issue publication packet",
        )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_github/readonly_SKILL.md",
            "Before `gh issue create`",
            "`compose-issue` issue publication packet",
            "gh issue create --type <IssueType>",
            "do not silently fall back to labels-only creation",
            "issue type via GraphQL",
        )

    def test_compose_pr_preserves_context_and_test_plan_gates(self):
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_compose-pr/readonly_SKILL.md",
            "PR title/body or PR publication packet",
            "The gate is not complete from previews or sliced fields",
            "PR Test Plan completeness gate",
            "include the expected observable result after the fix",
            "PR publication packet",
            "pending_approval",
        )

    def test_kibana_domain_owns_pr_title_and_metadata_boundaries(self):
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_elastic-domain/readonly_SKILL.md",
            "generic skills must not invent fallback Kibana title style, labels, release-note state, or footer policy",
            "PR titles should use Kibana's bracketed area style",
            "Do not use a Conventional Commit header as the PR title",
        )

    def test_kibana_label_guidance_blocks_esql_label_from_console_mentions(self):
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_kibana-labels-propose/readonly_SKILL.md",
            "this skill is the source of truth for `elastic/kibana` label/backport/version classification",
            "when all changed paths and the linked issue point to Console, propose `Feature:Console`",
            "do not add `Feature:ES|QL` unless there is separate evidence",
            "pending_approval",
        )

    def test_git_commit_style_does_not_control_pr_titles(self):
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_git/readonly_SKILL.md",
            "commit-message style does not transfer to PR titles",
            "PR titles are owned by `github` plus any verified domain overlay",
        )

    def test_github_skill_extracts_pr_review_and_sub_issue_references(self):
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_github/readonly_SKILL.md",
            "`~/.agents/skills/github/references/pr-reviews.md`",
            "`~/.agents/skills/github/references/pr-comments.md`",
            "`~/.agents/skills/github/references/sub-issues.md`",
        )
        self.assert_file_not_contains(
            "home/exact_dot_agents/exact_skills/exact_github/readonly_SKILL.md",
            "Add a soft close such as `Wdyt`",
            "Mutations: `addSubIssue`, `removeSubIssue`, `reprioritizeSubIssue`",
            "Practical constraint: GitHub generally allows only one",
        )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_github/exact_references/readonly_pr-reviews.md",
            "NEVER include `event` in the create-review payload",
            "Practical constraint: GitHub generally allows only one `PENDING` review per user per PR",
        )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_github/exact_references/readonly_pr-comments.md",
            "Add a soft close such as `Wdyt` only when the review style calls for it",
        )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_github/exact_references/readonly_sub-issues.md",
            "Mutations: `addSubIssue`, `removeSubIssue`, `reprioritizeSubIssue`",
        )

    def test_elastic_domain_skill_extracts_pr_issue_templates_reference(self):
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_elastic-domain/readonly_SKILL.md",
            "`~/.agents/skills/elastic-domain/references/pr-issue-templates.md`",
            "include environment details when UI or deployment matters",
            "leave unknown stack/deployment/browser fields blank or marked for follow-up; do not invent them",
        )
        self.assert_file_not_contains(
            "home/exact_dot_agents/exact_skills/exact_elastic-domain/readonly_SKILL.md",
            "## PR template: Bugfix",
            "## Issue template: Kibana",
            "Single sentence describing the user-facing behavior change.",
        )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_elastic-domain/exact_references/readonly_pr-issue-templates.md",
            "## PR template: Bugfix",
            "## Issue template: Kibana",
            "Single sentence describing the user-facing behavior change.",
        )

    def test_kbn_backport_skill_extracts_conflict_resolution_reference(self):
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_kbn-backport/readonly_SKILL.md",
            "`~/.agents/skills/kbn-backport/references/conflict-resolution.md`",
            "Triggered only when the run pauses with a conflict on the current target branch.",
            "Apply The Resolution, in `references/conflict-resolution.md`",
            "Validation (`references/conflict-resolution.md`) so the verifiers actually run and pass",
        )
        self.assert_file_not_contains(
            "home/exact_dot_agents/exact_skills/exact_kbn-backport/readonly_SKILL.md",
            "## Understand The Original Change",
            "## Resolution Rules",
            "node scripts/jest --config=",
        )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_kbn-backport/exact_references/readonly_conflict-resolution.md",
            "## Understand The Original Change",
            "## Resolution Rules",
            "node scripts/jest --config=<package>/jest.config.js <test-file>",
        )

    def test_ralph_skill_extracts_dashboard_tui_reference(self):
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_ralph/SKILL.md",
            "`~/.agents/skills/ralph/references/dashboard-tui.md`",
            "Default layout: runs list (left), run detail + roles table (top right), live tail of the selected role's output (bottom right).",
        )
        self.assert_file_not_contains(
            "home/exact_dot_agents/exact_skills/exact_ralph/SKILL.md",
            "## Fleet view (left pane)",
            "## KB browser",
            "opens an AI KB search modal",
        )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_ralph/exact_references/readonly_dashboard-tui.md",
            "## Fleet view (left pane)",
            "## KB browser",
            "opens an AI KB search modal",
        )

    def test_letsfg_skill_extracts_flexible_date_search_reference(self):
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_letsfg/readonly_SKILL.md",
            "`~/.agents/skills/letsfg/references/flexible-date-search.md`",
        )
        self.assert_file_not_contains(
            "home/exact_dot_agents/exact_skills/exact_letsfg/readonly_SKILL.md",
            "from concurrent.futures import ThreadPoolExecutor",
            "ThreadPoolExecutor(max_workers=min(2, len(dates)))",
        )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_letsfg/exact_references/readonly_flexible-date-search.md",
            "from concurrent.futures import ThreadPoolExecutor",
            "ThreadPoolExecutor(max_workers=min(2, len(dates)))",
        )

    def test_agent_review_dedups_restated_worker_descriptions_keeps_controller_validation(self):
        self.assert_file_not_contains(
            "home/exact_dot_agents/exact_skills/exact_agent-review/readonly_SKILL.md",
            "is part of the default flow after the blocking PR necessity gate",
            "is part of the PR-mode flow for other-authored or unknown-author PRs",
        )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_agent-review/readonly_SKILL.md",
            "Controller validation: reject and rerun any `live-ui-review` result that:",
            "uses the controller cwd or base/main runtime as the PR/head target for an explicit PR/branch review without proving that checkout is on the reviewed PR/head branch/sha",
            "Do not reject or rerun a result that reports a valid Playwriter harness blocker:",
            "`~/.agents/skills/agent-review/references/pr-necessity-auditor.md`",
            "`~/.agents/skills/agent-review/references/live-ui-review.md`",
        )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_agent-review/exact_references/readonly_pr-necessity-auditor.md",
            "Strictly read-only: never edit files, never run state-changing commands, never post or submit to GitHub.",
        )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_agent-review/exact_references/readonly_live-ui-review.md",
            "### Playwriter comparison",
        )

    def test_agent_review_fresh_eyes_uses_registry_lane_model(self):
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_agent-review/readonly_SKILL.md",
            "generic fresh-eyes is the only lane launch that passes the registry lane model at runtime",
            "model_required=<registry value|inherit|default>",
        )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_agent-review/exact_references/readonly_runtime-harnesses.md",
            "Generic fresh-eyes launches must pass the registry lane model as the profile-equivalent model",
            "never let the runtime pick an implicit default",
        )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_agent-review/exact_references/readonly_fresh-eyes.md",
            "pass the registry lane model explicitly",
            "model_required=<registry lanes value|inherit|default>",
            "model_status=exact",
        )
        self.assert_file_not_contains(
            "home/exact_dot_agents/exact_skills/exact_agent-review/exact_references/readonly_fresh-eyes.md",
            "model_required=n/a",
            "model_status=n/a",
        )

    def test_live_ui_windows_is_manual_only_and_purged_from_automatic_flows(self):
        # The Windows/VirtualBox environment is a standalone manual-only skill now;
        # `/agent-review`, `/build`, `live-ui-review`, and `ui-proof` must carry none of its
        # auto-inference or environment-selection machinery.
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_live-ui-windows/readonly_SKILL.md",
            "disable-model-invocation: true",
            "## Manual only — never automatic",
            "Load this skill only when the user explicitly asks, this turn, for Windows/VirtualBox verification",
            "~/.cache/live-ui-windows/registry.json",
            "start it with `VBoxManage startvm <vm> --type headless`",
            'match the line whose `guest port` equals that debug port, not just the first "Rule" match',
            "Never install Guest Additions or otherwise modify guest OS configuration",
        )
        self.assert_file_not_contains(
            "home/exact_dot_agents/exact_skills/exact_agent-review/exact_references/readonly_live-ui-runtime.md",
            "Environment selection",
            "windows_additional",
            "windows_only",
            "VBoxManage",
            "Windows",
            "VirtualBox",
        )
        self.assert_file_not_contains(
            "home/exact_dot_agents/exact_skills/exact_agent-review/exact_references/readonly_live-ui-review.md",
            "windows verification requirement",
            "environments_checked",
        )
        self.assert_file_not_contains(
            "home/exact_dot_agents/exact_skills/exact_ui-proof/readonly_SKILL.md",
            "windows verification requirement",
            "environments_checked",
        )
        self.assert_file_not_contains(
            "home/exact_dot_agents/exact_skills/exact_agent-review/readonly_SKILL.md",
            "Resolve the Windows/VirtualBox verification requirement once",
        )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_agent-review/readonly_SKILL.md",
            "Windows/VirtualBox coverage is out of scope for this flow: `live-ui-review` verifies the local browser only.",
            "add the manual `~/.agents/skills/live-ui-windows/SKILL.md` skill to this turn's work by hand",
        )
        self.assert_file_not_contains(
            "home/exact_dot_agents/exact_skills/exact_build/readonly_SKILL.md",
            "the resolved windows verification requirement",
        )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_build/readonly_SKILL.md",
            "`ui-proof` verifies the local browser only; when the user explicitly wants Windows/VirtualBox coverage too, add the manual `~/.agents/skills/live-ui-windows/SKILL.md` skill",
        )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_elastic-domain/exact_references/readonly_kibana-live-ui.md",
            "## Windows/VirtualBox environment translation",
            "Only applies when the manually-invoked `~/.agents/skills/live-ui-windows/SKILL.md` skill is used against a Kibana target.",
            "rewrite `kbn_url`'s hostname to VirtualBox's NAT gateway alias `10.0.2.2`",
            "Leave `es_url` untouched",
            "Add `server.host=0.0.0.0` to `required_kbn_flags`",
        )


class TestUvToolsHook(unittest.TestCase):
    """WHEN reconciling uv tool package specs."""

    def test_reapplies_complex_specs_instead_of_key_only_skip(self):
        hook = (REPO / "home/.chezmoiscripts/run_onchange_after_06-update-uv-tools.sh.tmpl").read_text()

        assert "uv_spec_requires_reapply()" in hook
        assert '[[ "$spec" != "$key" ]]' in hook
        assert "install_args+=(--force)" in hook
        assert "reapplying declared spec" in hook


if __name__ == "__main__":
    unittest.main()
