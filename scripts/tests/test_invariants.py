#!/usr/bin/env python3
"""Tests for repository instruction and hook invariants."""

from __future__ import annotations

import ast
import re
import unittest
from pathlib import Path

import _test_support  # noqa: F401  (puts scripts/ on sys.path)
from _test_support import REPO

SCRIPTS = REPO / "scripts"
LOCAL_SCRIPT_RE = re.compile(r"(?<![A-Za-z0-9_.-])([A-Za-z0-9_.-]+\.(?:py|sh))(?![A-Za-z0-9_.-])")
HOOK_SCRIPT_REF_RE = re.compile(r"\.\./scripts/([A-Za-z0-9_.-]+\.(?:py|sh))")
HASH_EXPRESSION_RE = re.compile(r"(?:sha256sum|shasum\s+-a\s+256)")


def _local_transform_dependencies(path: Path) -> set[Path]:
    if not path.is_file():
        raise AssertionError(f"missing local transform: {path}")
    if path.suffix == ".sh":
        return {
            SCRIPTS / name for name in LOCAL_SCRIPT_RE.findall(path.read_text(encoding="utf-8")) if name != path.name
        }

    modules = {candidate.stem: candidate for candidate in SCRIPTS.glob("*.py")}
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    dependencies: set[Path] = set()
    for node in ast.walk(tree):
        names: list[str] = []
        if isinstance(node, ast.Import):
            names.extend(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.append(node.module.split(".", 1)[0])
        dependencies.update(modules[name] for name in names if name in modules)
    return dependencies


def _transform_closure(paths: set[Path]) -> set[Path]:
    pending = list(paths)
    result: set[Path] = set()
    while pending:
        path = pending.pop()
        if path in result:
            continue
        if not path.is_file():
            raise AssertionError(f"missing local transform: {path}")
        result.add(path)
        pending.extend(_local_transform_dependencies(path) - result)
    return result


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
            "A repo-external `,proof` ledger is a durable receipt, not verification itself",
            "are not ledger triggers by themselves",
            "Do not create a ledger retroactively near the final answer",
            "do not invoke `,proof` merely because the task feels",
            "repo-external `,proof` ledger",
            "Test-first framing does not license touching code outside the request",
            "Before calling such behavior final or merge-ready",
            "Reuse an existing harness only after reading its manifest",
            "Compare implementation behavior against an independent model/table",
            "this verifies complexity, not a reason to add production state machines",
        )

    def test_skill_namespace_uses_k_prefix(self):
        # Copilot CLI validates the frontmatter `name` (dir name as fallback) and silently
        # drops leading `,`/`_`/`.`/`-`; dir-keyed harnesses (Claude/opencode/pi) use the
        # directory name. The uniform `k-` namespace avoids native-skill collisions in both,
        # so every skill dir and its frontmatter name must carry it.
        skills_root = REPO / "home/exact_dot_agents/exact_skills"
        name_re = re.compile(r"^name: \"?(?P<name>[^\"\n]+)\"?$", re.M)
        for skill_dir in sorted(p for p in skills_root.iterdir() if p.is_dir()):
            assert skill_dir.name.startswith("exact_k-"), f"skill dir missing k- namespace: {skill_dir.name}"
            expected = skill_dir.name.removeprefix("exact_")
            entry = next(
                (skill_dir / c for c in ("readonly_SKILL.md", "SKILL.md") if (skill_dir / c).is_file()),
                None,
            )
            if entry is None:
                # symlink_SKILL.md points at an externally owned file; the dir prefix is
                # all this repo controls (e.g. codesift-code-search).
                assert (skill_dir / "symlink_SKILL.md").is_file(), f"{skill_dir.name} has no SKILL entrypoint"
                continue
            match = name_re.search(entry.read_text(encoding="utf-8"))
            assert match, f"{entry} has no frontmatter name"
            assert match.group("name") == expected, f"{entry} frontmatter name {match.group('name')!r} != {expected!r}"

    def test_proof_access_requires_a_receipt_consumer_or_audit_need(self):
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-proof/readonly_SKILL.md",
            "Use only for non-review/non-build freeform work",
            "No other task property is a trigger by itself",
            "Do not create a ledger near the final answer",
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
        )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-compose-pr/readonly_SKILL.md",
            "Consume it as completion proof only when `allowed` is true, `finalized_at` is set, and `seal_status` is `ok`",
            "do not present it as proof or finish it retroactively during PR composition",
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

    def test_ai_docs_track_current_runtime_contracts(self):
        self.assert_file_contains(
            "docs/topics/ai-assistants/tool-configs/other-harnesses.md",
            "injects a bearer token minted by cursor-cli per request",
            "`,copilot` is a thin exec of the real binary",
            "The bearer-free `~/.copilot/mcp-config.json`",
        )
        self.assert_file_not_contains(
            "docs/topics/ai-assistants/tool-configs/other-harnesses.md",
            "Before launch, `,copilot` holds a private config lock",
            "sends the Authorization values to a single generator render over stdin",
            "The token-bearing `~/.copilot/mcp-config.json`",
        )
        self.assert_file_contains(
            "docs/topics/ai-assistants/tool-configs/profile-merging.md",
            "Copilot MCP rendering is apply-time only",
            "Runtime `,copilot` does not render config or change the ledger",
        )
        self.assert_file_contains(
            "docs/topics/ai-assistants/llama-cpp/launchers.md",
            "Hosted MCP authentication is owned by the per-request stdio bridges",
        )
        self.assert_file_not_contains(
            "docs/topics/ai-assistants/llama-cpp/launchers.md",
            "refreshes any configured Codex hosted-MCP bearer-token env vars",
            "after the MCP env-var setup",
        )
        self.assert_file_contains(
            "docs/topics/ai-assistants/mcp.md",
            "emitted to every work-profile harness, including Copilot and Codex",
            "OpenCode gets `scsi-local` only",
            "HTTP entries are intentionally skipped",
        )
        self.assert_file_contains(
            "docs/topics/ai-assistants/tool-configs/claude-gemini.md",
            "`alwaysThinkingEnabled: false`; `effortLevel: xhigh`",
        )
        self.assert_file_contains(
            "home/readonly_AGENTS.md",
            "a `holding` legion carries one actionable condition",
            "to resume the stored stage",
        )
        self.assert_file_contains(
            ".mermaids/04-palantir-state-machine.mmd",
            "holding --> resume : ,palantir answer uses stored resume_stage",
            "resume --> implement : implement / exhausted retry budget",
        )
        self.assert_file_not_contains(
            "docs/topics/ai-assistants/scenarios.md",
            "`/improve-…`",
            "**anything → compose-issue.**",
        )
        self.assert_file_not_contains(
            ".mermaids/03-agentic-os.mmd",
            "readonly_CLAUDE.md",
            "readonly_GEMINI.md",
        )
        self.assert_file_not_contains(
            ".mermaids/11-scripts-helpers.mmd",
            "Copilot typed header-auth plan + stdin override render",
        )
        self.assert_file_not_contains(
            ".mermaids/SR-index.mmd",
            "re-apply hook 06",
            "source: readonly_*",
            "keep 3 entrypoints in sync",
        )

    def test_global_sop_keeps_side_effect_publication_and_git_gates(self):
        self.assert_file_contains(
            "home/readonly_AGENTS.md",
            "Never run `git commit` unless the user explicitly requested a commit in the current conversation",
            "Content approval is not commit authorization",
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
            "load `~/.agents/skills/k-code-quality",
            "load `~/.agents/skills/k-communication/SKILL.md`",
            "load `~/.agents/skills/k-ai-kb/SKILL.md`",
            "load `~/.agents/skills/k-elastic-domain/SKILL.md`",
            "For human-visible text for anyone other than the in-session user, load",
        )

    def test_ai_kb_skill_owns_quoting_caveat_not_sop(self):
        # Shell-quoting for `,ai-kb remember` arguments is mechanical and command-specific
        # with a loud failure mode (shell error or garbled capsule), not universal or silent.
        # It belongs in the skill, not the always-on SOP.
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-ai-kb/readonly_SKILL.md",
            "Markdown backticks trigger shell command substitution unless single-quoted or escaped",
            "Never place unescaped backticks inside a double-quoted shell argument",
        )
        self.assert_file_not_contains(
            "home/readonly_AGENTS.md",
            "Never place unescaped backticks inside a double-quoted shell argument",
        )

    def test_code_quality_skills_preserve_extracted_style_guidance(self):
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-code-quality/readonly_SKILL.md",
            "Use when editing, reviewing, or refactoring implementation code in any language",
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
            "Use when editing, reviewing, or refactoring browser-rendered markup, styling, or presentation",
            "## Secondary Skill Escalation",
            "If the concrete web surface is React/JSX/TSX, also load the `~/.agents/skills/k-code-quality-react/SKILL.md` skill.",
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

        code_quality = (REPO / "home/exact_dot_agents/exact_skills/exact_k-code-quality/readonly_SKILL.md").read_text(
            encoding="utf-8"
        )
        first_actions = code_quality.split("## General Code Rules", 1)[0]
        assert "also load the `~/.agents/skills/k-code-quality-react/SKILL.md` skill" not in first_actions
        assert "also load the `~/.agents/skills/k-code-quality-tests/SKILL.md` skill" not in first_actions
        assert "also load the `~/.agents/skills/k-code-quality-web/SKILL.md` skill" not in first_actions
        assert "also load the `~/.agents/skills/k-codebase-design/SKILL.md` skill" not in first_actions

    def test_github_pr_publication_requires_preflight_and_readback_comparison(self):
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-github/readonly_SKILL.md",
            "PR creation is a composition action; it is not exempt.",
            "show a PR publication preflight ledger",
            'Approval to "create a PR" authorizes the GitHub side effect, but not invented human-visible content.',
            "Compare each field against the approved preflight ledger",
        )

    def test_issue_publication_requires_type_packet(self):
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-compose-issue/readonly_SKILL.md",
            "issue title/body or issue publication packet",
            "issue publication packet",
            "`issue_type`: exact GitHub issue type",
            "labels do not satisfy it",
            "pick from the repo's actual issue types",
            "Return the issue title/body draft and the issue publication packet",
        )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-github/readonly_SKILL.md",
            "Before `gh issue create`",
            "`k-compose-issue` issue publication packet",
            "gh issue create --type <IssueType>",
            "do not silently fall back to labels-only creation",
            "issue type via GraphQL",
        )

    def test_compose_pr_preserves_context_and_test_plan_gates(self):
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-compose-pr/readonly_SKILL.md",
            "PR title/body or PR publication packet",
            "The gate is not complete from previews or sliced fields",
            "PR Test Plan completeness gate",
            "include the expected observable result after the fix",
            "PR publication packet",
            "pending_approval",
        )

    def test_kibana_domain_owns_pr_title_and_metadata_boundaries(self):
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-elastic-domain/readonly_SKILL.md",
            "generic skills must not invent fallback Kibana title style, labels, release-note state, or footer policy",
            "PR titles should use Kibana's bracketed area style",
            "Do not use a Conventional Commit header as the PR title",
        )

    def test_kibana_label_guidance_blocks_esql_label_from_console_mentions(self):
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-kibana-labels-propose/readonly_SKILL.md",
            "this skill is the source of truth for `elastic/kibana` label/backport/version classification",
            "when all changed paths and the linked issue point to Console, propose `Feature:Console`",
            "do not add `Feature:ES|QL` unless there is separate evidence",
            "pending_approval",
        )

    def test_git_commit_style_does_not_control_pr_titles(self):
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-git/readonly_SKILL.md",
            "commit-message style does not transfer to PR titles",
            "PR titles are owned by `k-github` plus any verified domain overlay",
        )

    def test_github_skill_extracts_pr_review_and_sub_issue_references(self):
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-github/readonly_SKILL.md",
            "`~/.agents/skills/k-github/references/pr-reviews.md`",
            "`~/.agents/skills/k-github/references/pr-comments.md`",
            "`~/.agents/skills/k-github/references/sub-issues.md`",
        )
        self.assert_file_not_contains(
            "home/exact_dot_agents/exact_skills/exact_k-github/readonly_SKILL.md",
            "Add a soft close such as `Wdyt`",
            "Mutations: `addSubIssue`, `removeSubIssue`, `reprioritizeSubIssue`",
            "Practical constraint: GitHub generally allows only one",
        )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-github/exact_references/readonly_pr-reviews.md",
            "NEVER include `event` in the create-review payload",
            "Practical constraint: GitHub generally allows only one `PENDING` review per user per PR",
        )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-github/exact_references/readonly_pr-comments.md",
            "Add a soft close such as `Wdyt` only when the review style calls for it",
        )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-github/exact_references/readonly_sub-issues.md",
            "Mutations: `addSubIssue`, `removeSubIssue`, `reprioritizeSubIssue`",
        )

    def test_elastic_domain_skill_extracts_pr_issue_templates_reference(self):
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-elastic-domain/readonly_SKILL.md",
            "`~/.agents/skills/k-elastic-domain/references/pr-issue-templates.md`",
            "include environment details when UI or deployment matters",
            "leave unknown stack/deployment/browser fields blank or marked for follow-up; do not invent them",
        )
        self.assert_file_not_contains(
            "home/exact_dot_agents/exact_skills/exact_k-elastic-domain/readonly_SKILL.md",
            "## PR template: Bugfix",
            "## Issue template: Kibana",
            "Single sentence describing the user-facing behavior change.",
        )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-elastic-domain/exact_references/readonly_pr-issue-templates.md",
            "## PR template: Bugfix",
            "## Issue template: Kibana",
            "Single sentence describing the user-facing behavior change.",
        )

    def test_kbn_backport_skill_extracts_conflict_resolution_reference(self):
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-kbn-backport/readonly_SKILL.md",
            "`~/.agents/skills/k-kbn-backport/references/conflict-resolution.md`",
            "Triggered only when the run pauses with a conflict on the current target branch.",
            "Apply The Resolution, in `references/conflict-resolution.md`",
            "Validation (`references/conflict-resolution.md`) so the verifiers actually run and pass",
        )
        self.assert_file_not_contains(
            "home/exact_dot_agents/exact_skills/exact_k-kbn-backport/readonly_SKILL.md",
            "## Understand The Original Change",
            "## Resolution Rules",
            "node scripts/jest --config=",
        )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-kbn-backport/exact_references/readonly_conflict-resolution.md",
            "## Understand The Original Change",
            "## Resolution Rules",
            "node scripts/jest --config=<package>/jest.config.js <test-file>",
        )

    def test_letsfg_skill_extracts_flexible_date_search_reference(self):
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-letsfg/readonly_SKILL.md",
            "`~/.agents/skills/k-letsfg/references/flexible-date-search.md`",
        )
        self.assert_file_not_contains(
            "home/exact_dot_agents/exact_skills/exact_k-letsfg/readonly_SKILL.md",
            "from concurrent.futures import ThreadPoolExecutor",
            "ThreadPoolExecutor(max_workers=min(2, len(dates)))",
        )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-letsfg/exact_references/readonly_flexible-date-search.md",
            "from concurrent.futures import ThreadPoolExecutor",
            "ThreadPoolExecutor(max_workers=min(2, len(dates)))",
        )

    def test_agent_review_dedups_restated_worker_descriptions_keeps_controller_validation(self):
        self.assert_file_not_contains(
            "home/exact_dot_agents/exact_skills/exact_k-agent-review/readonly_SKILL.md",
            "is part of the default flow after the blocking PR necessity gate",
            "is part of the PR-mode flow for other-authored or unknown-author PRs",
        )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-agent-review/readonly_SKILL.md",
            "Controller validation: reject and rerun any `live-ui-review` result that:",
            "uses the controller cwd or base/main runtime as the PR/head target for an explicit PR/branch review without proving that checkout is on the reviewed PR/head branch/sha",
            "Do not reject or rerun a result that reports a valid Playwriter harness blocker:",
            "`~/.agents/skills/k-agent-review/references/pr-necessity-auditor.md`",
            "`~/.agents/skills/k-agent-review/references/live-ui-review.md`",
        )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-agent-review/exact_references/readonly_pr-necessity-auditor.md",
            "Strictly read-only: never edit files, never run state-changing commands, never post or submit to GitHub.",
        )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-agent-review/exact_references/readonly_live-ui-review.md",
            "### Playwriter comparison",
        )

    def test_agent_review_fresh_eyes_uses_registry_lane_model(self):
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-agent-review/readonly_SKILL.md",
            "generic fresh-eyes is the only lane launch that passes the registry lane model at runtime",
            "model_required=<registry value|inherit|default>",
        )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-agent-review/exact_references/readonly_runtime-harnesses.md",
            "Generic fresh-eyes launches must pass the registry lane model as the profile-equivalent model",
            "never let the runtime pick an implicit default",
        )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-agent-review/exact_references/readonly_fresh-eyes.md",
            "pass the registry lane model explicitly",
            "model_required=<registry lanes value|inherit|default>",
            "model_status=exact",
        )
        self.assert_file_not_contains(
            "home/exact_dot_agents/exact_skills/exact_k-agent-review/exact_references/readonly_fresh-eyes.md",
            "model_required=n/a",
            "model_status=n/a",
        )

    def test_live_ui_windows_is_manual_only_and_purged_from_automatic_flows(self):
        # The Windows/VirtualBox environment is a standalone manual-only skill now;
        # `/k-agent-review`, `/k-build`, `live-ui-review`, and `ui-proof` must carry none of its
        # auto-inference or environment-selection machinery.
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-live-ui-windows/readonly_SKILL.md",
            "disable-model-invocation: true",
            "## Manual only — never automatic",
            "Load this skill only when the user explicitly asks, this turn, for Windows/VirtualBox verification",
            "~/.cache/live-ui-windows/registry.json",
            "start it with `VBoxManage startvm <vm> --type headless`",
            'match the line whose `guest port` equals that debug port, not just the first "Rule" match',
            "Never install Guest Additions or otherwise modify guest OS configuration",
        )
        self.assert_file_not_contains(
            "home/exact_dot_agents/exact_skills/exact_k-agent-review/exact_references/readonly_live-ui-runtime.md",
            "Environment selection",
            "windows_additional",
            "windows_only",
            "VBoxManage",
            "Windows",
            "VirtualBox",
        )
        self.assert_file_not_contains(
            "home/exact_dot_agents/exact_skills/exact_k-agent-review/exact_references/readonly_live-ui-review.md",
            "windows verification requirement",
            "environments_checked",
        )
        self.assert_file_not_contains(
            "home/exact_dot_agents/exact_skills/exact_k-ui-proof/readonly_SKILL.md",
            "windows verification requirement",
            "environments_checked",
        )
        self.assert_file_not_contains(
            "home/exact_dot_agents/exact_skills/exact_k-agent-review/readonly_SKILL.md",
            "Resolve the Windows/VirtualBox verification requirement once",
        )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-agent-review/readonly_SKILL.md",
            "Windows/VirtualBox coverage is out of scope for this flow: `live-ui-review` verifies the local browser only.",
            "add the manual `~/.agents/skills/k-live-ui-windows/SKILL.md` skill to this turn's work by hand",
        )
        self.assert_file_not_contains(
            "home/exact_dot_agents/exact_skills/exact_k-build/readonly_SKILL.md",
            "the resolved windows verification requirement",
        )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-build/readonly_SKILL.md",
            "`k-ui-proof` verifies the local browser only; when the user explicitly wants Windows/VirtualBox coverage too, add the manual `~/.agents/skills/k-live-ui-windows/SKILL.md` skill",
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
            "Use when the agent is about to make a material rewrite of human-maintained prose",
            "## Automatic in normal iteration",
            "Run automatically only when the target has multiple materially different",
            "State a short rubric",
            "Do not use for code, generated artifacts, configuration, secret-bearing content, runtime/system behavior",
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


class TestUvToolsHook(unittest.TestCase):
    """WHEN reconciling uv tool package specs."""

    def test_reapplies_complex_specs_instead_of_key_only_skip(self):
        hook = (REPO / "home/.chezmoiscripts/run_onchange_after_06-update-uv-tools.sh.tmpl").read_text()

        assert "uv_spec_requires_reapply()" in hook
        assert '[[ "$spec" != "$key" ]]' in hook
        assert "install_args+=(--force)" in hook
        assert "reapplying declared spec" in hook


class TestOnchangeHookHashClosure(unittest.TestCase):
    """WHEN hash-gated hooks call registry-backed helper scripts."""

    def test_SHOULD_hash_every_direct_and_transitive_local_transform(self):
        hooks = sorted((REPO / "home/.chezmoiscripts").glob("run_onchange_after_07-*.sh.tmpl"))
        self.assertTrue(hooks)
        failures: dict[str, list[str]] = {}
        for hook in hooks:
            lines = hook.read_text(encoding="utf-8").splitlines()
            direct = {
                SCRIPTS / name
                for line in lines
                if not HASH_EXPRESSION_RE.search(line)
                for name in HOOK_SCRIPT_REF_RE.findall(line)
            }
            required = {path.name for path in _transform_closure(direct)}
            hashed = {
                name for line in lines if HASH_EXPRESSION_RE.search(line) for name in HOOK_SCRIPT_REF_RE.findall(line)
            }
            missing = sorted(required - hashed)
            if missing:
                failures[hook.name] = missing
        self.assertEqual(failures, {})

    def test_SHOULD_keep_the_llama_sync_helper_in_the_hash_gate(self):
        hook = (REPO / "home/.chezmoiscripts/run_onchange_after_07-sync-llama-cpp-models.sh.tmpl").read_text()
        helper_hash_lines = [line for line in hook.splitlines() if "sync_llama_cpp_models.py" in line]
        self.assertTrue(any(HASH_EXPRESSION_RE.search(line) for line in helper_hash_lines))


if __name__ == "__main__":
    unittest.main()
