#!/usr/bin/env python3
"""Tests for repository instruction and hook invariants."""

from __future__ import annotations

import ast
import hashlib
import json
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


SOP_MANIFEST_PATH = "home/dot_config/ai/readonly_policy-manifest.v1.json"


def _sop_rule_text() -> str:
    """Return the compiled core SOP after checking manifest hash consistency.

    Stage 2 moves some rules to skill/hook/overlay consumers instead of
    home/readonly_AGENTS.md; frozen moved-rule text lives in the disposition
    records for provenance. Core assertions should read the actual generated
    core file, but fail first if the policy manifest hash is stale.
    """
    manifest = json.loads((REPO / SOP_MANIFEST_PATH).read_text(encoding="utf-8"))
    actual_core = (REPO / "home/readonly_AGENTS.md").read_text(encoding="utf-8")
    actual_hash = hashlib.sha256(actual_core.encode("utf-8")).hexdigest()
    if manifest.get("output_sha256") != actual_hash:
        raise AssertionError("policy manifest output_sha256 is stale relative to home/readonly_AGENTS.md")
    return actual_core


class TestAgentInstructionInvariants(unittest.TestCase):
    """WHEN guarding high-risk agent workflow instructions."""

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
            "This global SOP overrides weaker project-local SOP files",
            "project-local instructions may add constraints but must not weaken this SOP",
            "Continue working until the user's goal is complete",
            "Any premature stopping, including checkpoint commentary, is an operational failure",
        )

    def test_global_sop_keeps_truth_runtime_and_completion_gates(self):
        self.assert_file_contains(
            "home/readonly_AGENTS.md",
            "Every implementation summary must include: `Compatibility impact: none | removed (requested) | kept existing (requested)`",
            "with no shim, alias, wrapper, or deprecation path",
            "Do not build further reasoning on unverified external behavior",
            "label hypotheses explicitly and do not let them gate downstream steps",
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
            "every numeric literal in the claim must occur verbatim in that quote",
            "reject the unverifiable claim, not the source or entity",
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
            "Reframe tasks into observable checks when practical",
            "bug fixes get reproducing tests",
            "A repo-external `,proof` ledger is a durable receipt, not verification itself",
            "are not ledger triggers by themselves",
            "Do not create a ledger retroactively near the final answer",
            "do not invoke `,proof` merely because the task feels",
            "repo-external `,proof` ledger",
            "Test-first framing does not license touching code outside the request",
        )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-code-quality/readonly_SKILL.md",
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

    def test_pi_review_controller_named_roles_have_profiles(self):
        agents_dir = REPO / "home/dot_pi/agent/exact_agents"
        profiles = {path.name.removesuffix(".md.tmpl") for path in agents_dir.glob("*.md.tmpl")}
        controller = (agents_dir / "review-controller.md.tmpl").read_text(encoding="utf-8")
        required = {
            "reviewer",
            "fresh-eyes",
            "adversarial-verifier",
            "pr-necessity-auditor",
            "live-ui-review",
            "findings-auditor",
        }

        assert required <= profiles, f"Pi review controller references missing profiles: {sorted(required - profiles)}"
        for role in required:
            assert role in controller

    def test_pi_settings_use_native_shared_skills_and_real_extension_packages(self):
        for profile in ("work", "personal"):
            path = REPO / f"home/dot_pi/agent/readonly_settings.{profile}.json"
            settings = json.loads(path.read_text(encoding="utf-8"))
            assert settings["packages"] == [
                "~/.local/share/yarn/global/node_modules/pi-mcp-adapter",
                "~/.local/share/yarn/global/node_modules/pi-subagents",
            ]

    def test_proof_access_requires_a_receipt_consumer_or_audit_need(self):
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-proof/readonly_SKILL.md",
            "Use `,proof` only when at least one receipt trigger applies",
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
            "[OUTPUT DISCIPLINE]",
            "Length is a budget, not a vibe",
            "Direct answer ≤80 words",
            "Comparison/audit ≤120",
            "Reach for a density primitive before prose",
            "verdict line, delta table, anchor list",
            "emit a 1-line skeleton",
            "may not restate an item already in an earlier table/list",
            "Brevity outranks structure; structure must earn its space",
            "No valid model of time/effort/urgency",
        )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-compose-pr/exact_references/readonly_publication-packet.md",
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
            "`,copilot` passes through to the real binary except for bare `--resume`",
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
            "emitted to every work-profile harness, including OMP, Copilot, and Codex",
            "OpenCode gets `scsi-local` only",
            "HTTP entries are intentionally skipped",
        )
        self.assert_file_contains(
            "docs/topics/ai-assistants/tool-configs/claude-gemini.md",
            "`alwaysThinkingEnabled: false`; `effortLevel: xhigh`",
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
            "home/exact_dot_agents/exact_skills/exact_k-git/readonly_SKILL.md",
            "Never run `git commit` unless the user explicitly requested a commit in the current conversation",
            "Content approval is not commit authorization",
            "`git pull`, `git pull --rebase`, `git rebase <remote>/<branch>`, or `git merge <remote>/<branch>` automatically before pushing",
            "If push is rejected for divergence, non-fast-forward, lease failure, or diverged history, stop and ask how to proceed",
        )
        self.assert_file_contains(
            "home/readonly_AGENTS.md",
            "Never run `git commit` unless the user explicitly requested a commit in the current conversation",
            "content approval is not commit authorization",
            "git push --force-with-lease",
            "Never run `git pull`, `git pull --rebase`, `git rebase <remote>/<branch>`, or `git merge <remote>/<branch>` automatically before pushing",
            "If push is rejected for divergence, non-fast-forward, lease failure, or diverged history, stop and ask how to proceed",
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
            "Do not commit, reveal, or write secrets or plaintext credentials.",
            "Brevity outranks structure. Shortest form that carries the full meaning wins",
            "Structure must earn its space by adding scannable information not present elsewhere",
            "Length is a hard budget per task class, not a vibe",
            "Direct answer or one-shot question: ≤80",
            "Comparison or audit: ≤120",
            "Multi-part investigation: ≤200",
            "Cut words, never facts",
            "One idea per line",
            "You have no valid model of elapsed time, effort, or urgency",
            'no "due to time constraints"',
            "Never estimate duration",
            "Decide scope on evidence, correctness, risk, and explicit user constraints",
            "Line 1 answers; last line adds new information",
            "Reach for a density primitive before prose",
            "Verdict line",
            "Delta table",
            "Anchor list",
            "Decision block",
            "emit a 1-line skeleton first",
            "A later section may not restate an item already given in an earlier table/list",
            "cap at 5",
            "Anchor claims with evidence; do not narrate the verification chain in prose",
            "Choose no reply when it would only restate the thread",
            "Match the surface's register",
            "Use natural wording, or say that no message is worth sending",
            "One clarifying question per message",
            "Code citation format: `startLine:endLine:filepath`",
            "In-response result summary only when it carries evidence, outcomes, or next-step constraints",
            "### 6.6 Examples",
            'BAD: "I looked at the file',
            'GOOD: "X. See `file.py:42`."',
            "Pick Claude — only row with drift protection",
            'BAD: "For now, ship this quick fix',
            "Think laterally about root causes and indirect effects",
            "Do not stop at the first plausible explanation; verify thoroughly",
            '"Concise" means unpadded, not shallow.',
            "unnecessary churn is a defect, not diligence",
        )
        self.assert_file_contains(
            "home/readonly_AGENTS.md",
            "Recall first with `,ai-kb search` when prior knowledge could help",
            "never store guesses or session-only notes",
            "Mid-task decisions, ideas, and unverified constraints worth keeping go to `,agent-memory note",
            "At the end of any substantive turn, silently self-check whether a durable verified reusable insight was produced",
            "not a checkpoint and not a reason to stop early",
            "no announcement or separate summary",
            "No per-session cap; dedup before writing",
        )

    def test_review_flows_iterate_to_fixed_point(self):
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-review/exact_references/readonly_judging_core.md",
            "**Fixed point.**",
            "Repeat until no new surviving findings or hygiene findings remain",
            "Repeat until the four dimensions return clean",
            "verified blocker/Requirements Reset stops the loop",
        )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-build/readonly_SKILL.md",
            "Repeat the Post-Review Stage until it returns clean",
            "rerun packet checks and adversarial verification before reporting",
        )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-review/exact_references/readonly_local_changes.md",
            "following its fixed-point repeat rule until clean or blocked",
        )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-review/exact_references/readonly_pr_fix.md",
            "rerun current-head outcome verification for affected threads before completion",
        )
        self.assert_file_not_contains(
            "home/exact_dot_agents/exact_skills/exact_k-review/exact_references/readonly_local_changes.md",
            "Post-Review Stage once",
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
            "Use for browser-rendered markup, CSS, layout, visual states, accessibility, or focus behavior edits/reviews",
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
            "Load `~/.agents/skills/k-github/references/pr-create.md`",
            'Approval to "create a PR" authorizes the GitHub side effect, but not invented human-visible content.',
        )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-github/exact_references/readonly_pr-create.md",
            "Before the side effect, show:",
            "Compare each field against the approved preflight ledger",
        )

    def test_issue_publication_requires_type_packet(self):
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-compose-issue/readonly_SKILL.md",
            "issue title/body draft or issue publication packet",
            "issue publication packet",
            "`issue_type`: exact GitHub issue type",
            "labels do not satisfy it",
            "pick from the repo's actual issue types",
            "Return the issue title/body draft and the issue publication packet",
        )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-github/readonly_SKILL.md",
            "Load `~/.agents/skills/k-github/references/issue-create.md`",
            "issue type gate",
        )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-github/exact_references/readonly_issue-create.md",
            "Before `gh issue create`",
            "`k-compose-issue` issue publication packet",
            "gh issue create --type <IssueType>",
            "do not silently fall back to labels-only creation",
            "issue type via GraphQL",
        )

    def test_compose_pr_preserves_context_and_test_plan_gates(self):
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-compose-pr/readonly_SKILL.md",
            "PR title/body or publication packet",
            "Load `~/.agents/skills/k-compose-pr/references/publication-packet.md`",
            "PR publication packet",
        )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-compose-pr/exact_references/readonly_publication-packet.md",
            "The gate is not complete from previews or sliced fields",
            "PR Test Plan completeness gate",
            "include the expected observable result after the fix",
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

    def test_deep_review_dedups_restated_worker_descriptions_keeps_controller_validation(self):
        self.assert_file_not_contains(
            "home/exact_dot_agents/exact_skills/exact_k-deep-review/readonly_SKILL.md",
            "is part of the default flow after the blocking PR necessity gate",
            "is part of the PR-mode flow for other-authored or unknown-author PRs",
        )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-deep-review/readonly_SKILL.md",
            "Controller validation: reject and rerun any `live-ui-review` result that:",
            "uses the controller cwd or base/main runtime as the PR/head target for an explicit PR/branch review without proving that checkout is on the reviewed PR/head branch/sha",
            "Do not reject or rerun a result that reports a valid Playwriter harness blocker:",
            "`~/.agents/skills/k-review/references/pr-necessity-auditor.md`",
            "`~/.agents/skills/k-review/references/live-ui-review.md`",
        )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-review/exact_references/readonly_pr-necessity-auditor.md",
            "Strictly read-only: never edit files, never run state-changing commands, never post or submit to GitHub.",
        )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-review/exact_references/readonly_live-ui-review.md",
            "### Playwriter comparison",
        )

    def test_deep_review_fresh_eyes_uses_registry_lane_model(self):
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-deep-review/readonly_SKILL.md",
            "named fresh-eyes profiles and generic fresh-eyes launches both use the registry lane model",
            "model_required=<registry value|inherit|default>",
        )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-review/exact_references/readonly_runtime-harnesses.md",
            "Generic fresh-eyes launches must pass the registry lane model as the profile-equivalent model",
            "named fresh-eyes profiles carry the same registry-rendered frontmatter",
            "never let the runtime pick an implicit default",
        )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-review/exact_references/readonly_fresh-eyes.md",
            "Pi/OMP: launch the `fresh-eyes` agent profile",
            "model_required=<registry lanes value|inherit|default>",
            "model_status=exact",
        )
        self.assert_file_contains(
            "home/dot_pi/agent/exact_agents/fresh-eyes.md.tmpl",
            'model: "{{ .agent_review_models.pi.lanes }}"',
        )
        self.assert_file_contains(
            "home/dot_omp/private_agent/exact_agents/fresh-eyes.md.tmpl",
            'model: "{{ .agent_review_models.omp.lanes }}"',
        )
        self.assert_file_not_contains(
            "home/dot_pi/agent/exact_agents/fresh-eyes.md.tmpl",
            ".model_tier_map.pi.review.model",
        )
        self.assert_file_not_contains(
            "home/dot_omp/private_agent/exact_agents/fresh-eyes.md.tmpl",
            ".model_tier_map.omp.review.model",
        )
        self.assert_file_not_contains(
            "home/exact_dot_agents/exact_skills/exact_k-review/exact_references/readonly_fresh-eyes.md",
            "model_required=n/a",
            "model_status=n/a",
        )

    def test_findings_audit_precedes_final_adversarial_verification(self):
        # The audit narrows the candidate set and the cross-family verifier then refutes only
        # what survived. Reverting to the old parallel/adversarial-first order silently doubles
        # verifier work and lets refuted candidates reach the audit.
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-deep-review/readonly_SKILL.md",
            "5. findings audit, inline or delegated by the findings-audit delegation conditions",
            "6. final cross-family adversarial verification over the audited candidate set",
            "4. **Run controller findings audit on candidate findings.**",
            "5. **Run final adversarial verification.**",
            "Launch one to three sighted lanes by default.",
        )
        for mode_file, ordering in (
            (
                "exact_k-review/exact_references/readonly_local_changes.md",
                "Run the Findings-Set Audit from `judging_core.md` in the controller over the candidate set before adversarial verification.",
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
            "home/dot_pi/agent/exact_agents/review-controller.md.tmpl",
            "home/dot_omp/private_agent/exact_agents/review-controller.md.tmpl",
        ):
            self.assert_file_contains(
                controller,
                "## Phase 4 — Findings audit (delegate, read-only)",
                "## Phase 5 — Final adversarial verification (delegate, cross-family)",
            )
            # The audit runs before the verifier, so it cannot consume adversarial verdicts;
            # applying those verdicts belongs to the later reconcile phase.
            self.assert_file_not_contains(
                controller,
                "Findings audit reconciles adversarial and live-UI outputs",
            )

    def test_copilot_subagent_settings_match_the_review_model_registry(self):
        # Copilot resolves subagent models from ~/.copilot/settings.json, which a merge script
        # reads as source JSON, so it cannot be a chezmoi template over the registry. It is
        # hand-synced and has drifted before; this asserts it against agent_review_models.
        import ai_models

        registry = ai_models.load_agent_review_models(REPO / "home/.chezmoidata/ai_models.yaml")
        copilot = registry["copilot"]
        agents = json.loads((REPO / "home/private_dot_copilot/settings.json").read_text(encoding="utf-8"))["subagents"][
            "agents"
        ]

        lane_roles = (
            "deep-review",
            "review-worker",
            "findings-auditor",
            "pr-necessity-auditor",
            "live-ui-review",
        )
        # criteria-verifier is /k-build's refutation lane and shares the review verifier pick.
        verifier_roles = ("adversarial-verifier", "criteria-verifier")

        for role in lane_roles:
            assert agents[role]["model"] == copilot["lanes"], (
                f"copilot settings.json {role} model {agents[role]['model']!r} != "
                f"agent_review_models.copilot.lanes {copilot['lanes']!r}"
            )
        for role in verifier_roles:
            assert agents[role]["model"] == copilot["verifier"], (
                f"copilot settings.json {role} model {agents[role]['model']!r} != "
                f"agent_review_models.copilot.verifier {copilot['verifier']!r}"
            )
        # gpt-5.5 is only ever run at high effort, and Opus review lanes are pinned high too.
        for role in lane_roles + verifier_roles:
            assert agents[role]["effortLevel"] == "high", (
                f"copilot settings.json {role} effortLevel is {agents[role]['effortLevel']!r}, expected 'high'"
            )

    def test_model_tier_map_agrees_with_the_review_registry(self):
        # Two registries describe the same review picks: model_tier_map's review buckets and
        # agent_review_models. Only the latter is templated into agent profiles on most harnesses,
        # so a tier-map row can quietly describe a policy nothing implements. Pin them together.
        import ai_models

        path = REPO / "home/.chezmoidata/ai_models.yaml"
        tier_map = ai_models.load_model_tier_map(path)
        registry = ai_models.load_agent_review_models(path)
        # The tier map spells the Claude harness claude_code; the review registry spells it claude.
        registry_name = {"claude_code": "claude"}

        for harness, buckets in tier_map.items():
            roles = registry.get(registry_name.get(harness, harness))
            if roles is None:
                continue
            review = buckets.get("review", {}).get("model", "")
            verifier_bucket = buckets.get("adversarial_verification", {}).get("model", "")

            # Claude sessions launch on a deliberately chosen model, so its registry entry is
            # "inherit" and cannot be compared. No other harness may claim that exemption.
            if roles.get("lanes") == "inherit":
                assert harness == "claude_code", (
                    f"{harness} review registry is 'inherit'; only claude_code may be unpinned"
                )
            else:
                assert review == roles["lanes"], (
                    f"model_tier_map.{harness}.review is {review!r} but "
                    f"agent_review_models.{registry_name.get(harness, harness)}.lanes is {roles['lanes']!r}"
                )
                assert verifier_bucket == roles["verifier"], (
                    f"model_tier_map.{harness}.adversarial_verification is {verifier_bucket!r} but "
                    f"agent_review_models.{registry_name.get(harness, harness)}.verifier is {roles['verifier']!r}"
                )

            # The audit lanes read the same diff as the review lanes; they track the review pick.
            for bucket in ("findings_audit", "post_act_verification"):
                model = buckets.get(bucket, {}).get("model", "")
                assert model == review, f"model_tier_map.{harness}.{bucket} is {model!r} but review is {review!r}"

    def test_model_tier_map_orchestration_matches_real_harness_config(self):
        # The orchestration rows are the ones that reach a real config file. Claude Code's is
        # jq-patched into settings.json at apply time and Codex's is a hand-kept literal, so a
        # wrong row here ships silently to the session default.
        import ai_models

        tier_map = ai_models.load_model_tier_map(REPO / "home/.chezmoidata/ai_models.yaml")

        for profile in ("personal", "work"):
            row = tier_map["claude_code"][f"orchestration_{profile}"]
            settings = json.loads((REPO / f"home/dot_claude/settings.{profile}.json").read_text(encoding="utf-8"))
            assert settings["model"] == row["model"], (
                f"claude settings.{profile}.json model {settings['model']!r} != "
                f"model_tier_map.claude_code.orchestration_{profile}.model {row['model']!r}"
            )
            assert settings["effortLevel"] == row["effort"], (
                f"claude settings.{profile}.json effortLevel {settings['effortLevel']!r} != "
                f"model_tier_map.claude_code.orchestration_{profile}.effort {row['effort']!r}"
            )

            codex_row = tier_map["codex"]["orchestration"]
            config = (REPO / f"home/dot_codex/private_config.{profile}.toml").read_text(encoding="utf-8")
            model = re.search(r'^model\s*=\s*"([^"]+)"', config, re.M)
            effort = re.search(r'^model_reasoning_effort\s*=\s*"([^"]+)"', config, re.M)
            assert model and model.group(1) == codex_row["model"], (
                f"codex private_config.{profile}.toml model "
                f"{(model.group(1) if model else None)!r} != "
                f"model_tier_map.codex.orchestration.model {codex_row['model']!r}"
            )
            assert effort and effort.group(1) == codex_row["effort"], (
                f"codex private_config.{profile}.toml model_reasoning_effort "
                f"{(effort.group(1) if effort else None)!r} != "
                f"model_tier_map.codex.orchestration.effort {codex_row['effort']!r}"
            )

    def test_claude_code_models_are_claude_family_selectors(self):
        # Claude Code does not remap unknown model ids: they reach the API and come back as
        # "API model not found". A cross-vendor id here (e.g. a shared gpt-5.5 orchestration
        # default) silently breaks every native session once the merge script patches settings.json.
        import ai_models

        aliases = {"default", "opus", "opusplan", "sonnet", "haiku"}

        def claude_family(model: str) -> bool:
            base = re.sub(r"\[.*\]$", "", model)  # strip param suffixes like [1m]
            return base in aliases or base.startswith("claude-")

        def wrong_version_spelling(model: str) -> bool:
            # Claude Code hyphenates point versions. Its own 404 troubleshooting text names
            # `claude-sonnet-4.6` as the typo for `claude-sonnet-4-6`. Other harnesses (Copilot,
            # Cursor) do use the dotted form, so this spelling is only wrong on this harness.
            return bool(re.search(r"claude-\w+-\d+\.\d+", model))

        def check(where: str, model: str) -> None:
            assert claude_family(model), f"{where} is {model!r}, which Claude Code cannot run"
            hyphenated = re.sub(r"(claude-\w+-\d+)\.(\d+)", r"\1-\2", model)
            assert not wrong_version_spelling(model), (
                f"{where} is {model!r}; Claude Code hyphenates point versions "
                f"(expected {hyphenated!r}) and 404s on the dotted form"
            )

        tier_map = ai_models.load_model_tier_map(REPO / "home/.chezmoidata/ai_models.yaml")
        for bucket, row in tier_map["claude_code"].items():
            check(f"model_tier_map.claude_code.{bucket}", row.get("model", ""))

        for profile in ("personal", "work"):
            settings = json.loads((REPO / f"home/dot_claude/settings.{profile}.json").read_text(encoding="utf-8"))
            check(f"claude settings.{profile}.json model", settings.get("model", ""))

    def test_gpt55_is_always_pinned_at_high_effort(self):
        # Standing policy: gpt-5.5 is only ever run at high effort, in every harness and bucket.
        # The effort lives in a different place per harness (a yaml `effort`, a model-id suffix,
        # a `:thinking` suffix, model_reasoning_effort, effortLevel), so drift is easy and silent.
        import ai_models

        offenders: list[str] = []

        def check(where: str, model: str, effort: str | None) -> None:
            if "gpt-5.5" not in model or "gpt-5.5-codex" in model:
                return
            # Cursor bakes effort into the id; Pi/OMP use a `:level` suffix.
            suffix = re.search(r"gpt-5\.5[-:]([a-z-]+)", model)
            if suffix and suffix.group(1) not in ("high",):
                offenders.append(f"{where}: model {model!r} is not high effort")
            if effort is not None and effort != "high":
                offenders.append(f"{where}: effort {effort!r} is not high (model {model!r})")

        tier_map = ai_models.load_model_tier_map(REPO / "home/.chezmoidata/ai_models.yaml")
        for harness, buckets in tier_map.items():
            for bucket, row in buckets.items():
                check(f"model_tier_map.{harness}.{bucket}", row.get("model", ""), row.get("effort"))
                fallback = row.get("fallback")
                if isinstance(fallback, dict):
                    check(
                        f"model_tier_map.{harness}.{bucket}.fallback",
                        fallback.get("model", ""),
                        fallback.get("effort"),
                    )

        registry = ai_models.load_agent_review_models(REPO / "home/.chezmoidata/ai_models.yaml")
        for harness, roles in registry.items():
            for role, model in roles.items():
                check(f"agent_review_models.{harness}.{role}", model, None)

        copilot = json.loads((REPO / "home/private_dot_copilot/settings.json").read_text(encoding="utf-8"))
        for name, agent in copilot["subagents"]["agents"].items():
            check(f"copilot settings.json {name}", agent.get("model", ""), agent.get("effortLevel"))

        for profile in ("personal", "work"):
            claude = json.loads((REPO / f"home/dot_claude/settings.{profile}.json").read_text(encoding="utf-8"))
            check(f"claude settings.{profile}", claude.get("model", ""), claude.get("effortLevel"))

            codex = (REPO / f"home/dot_codex/private_config.{profile}.toml").read_text(encoding="utf-8")
            model = re.search(r'^model\s*=\s*"([^"]+)"', codex, re.M)
            effort = re.search(r'^model_reasoning_effort\s*=\s*"([^"]+)"', codex, re.M)
            if model:
                check(
                    f"codex private_config.{profile}.toml",
                    model.group(1),
                    effort.group(1) if effort else None,
                )

        assert not offenders, "gpt-5.5 must always run at high effort:\n  " + "\n  ".join(offenders)

    def test_model_tier_map_is_short_context_by_default(self):
        # Standing policy: short context everywhere. `long` is allowed only where the harness
        # publishes no short variant of the wanted model, which today is Cursor alone — it ships
        # Opus 5, Sonnet 5 and GPT-5.5 exclusively as 1M ids. Any other `long` row is drift, and
        # an empty value is worse: it reads as "nobody decided" and hides which window is in play.
        import ai_models

        cursor_1m_only = ("claude-opus-5", "claude-sonnet-5", "gpt-5.5")
        offenders: list[str] = []

        def check(where: str, harness: str, model: str, context: str | None) -> None:
            # Order matters: a 1M-only Cursor row claiming "short" is a lie about the window it
            # gets, so the forced-long case is checked before the short-by-default case.
            if harness == "cursor" and any(model.startswith(name) for name in cursor_1m_only):
                if context != "long":
                    offenders.append(
                        f"{where}: {model!r} is 1M-only on Cursor, so context must be 'long', got {context!r}"
                    )
                return
            if context != "short":
                offenders.append(f"{where}: context is {context!r}, expected 'short' (model {model!r})")

        tier_map = ai_models.load_model_tier_map(REPO / "home/.chezmoidata/ai_models.yaml")
        for harness, buckets in tier_map.items():
            for bucket, row in buckets.items():
                check(f"model_tier_map.{harness}.{bucket}", harness, row.get("model", ""), row.get("context"))
                fallback = row.get("fallback")
                if isinstance(fallback, dict):
                    check(
                        f"model_tier_map.{harness}.{bucket}.fallback",
                        harness,
                        fallback.get("model", ""),
                        fallback.get("context"),
                    )

        # Copilot's contextTier is the only dial that turns the policy into a runtime request.
        copilot = json.loads((REPO / "home/private_dot_copilot/settings.json").read_text(encoding="utf-8"))
        for name, agent in copilot["subagents"]["agents"].items():
            tier = agent.get("contextTier")
            if tier != "default":
                offenders.append(f"copilot settings.json {name}: contextTier is {tier!r}, expected 'default'")

        # `[1m]` is the Claude Code selector that swaps a bare id onto the gateway's 1M window.
        for relative in ("home/exact_bin/executable_,claude-litellm", "home/dot_config/fish/readonly_config.fish.tmpl"):
            source = (REPO / relative).read_text(encoding="utf-8")
            code = "\n".join(line for line in source.splitlines() if not line.lstrip().startswith("#"))
            if "[1m]" in code:
                offenders.append(f"{relative}: carries a [1m] extended-context selector")

        assert not offenders, "short context is the default everywhere:\n  " + "\n  ".join(offenders)

    def test_gruntwork_runs_the_codex_tier_wherever_the_catalog_has_it(self):
        # Gruntwork is the cheap bucket, so it takes gpt-5.3-codex at high effort on every harness
        # whose catalog carries it. Claude Code and Gemini are single-vendor and cannot, and native
        # Codex has no gpt-5.3-codex-spark, so each keeps its own pick — spelled out here so a
        # future edit cannot quietly downgrade a harness that could have run the codex tier.
        import ai_models

        expected = {
            "claude_code": "claude-sonnet-4-6",  # Anthropic-only catalog
            "codex": "gpt-5.4",  # no gpt-5.3-codex-spark in the 0.146.0 catalog
            "copilot": "gpt-5.3-codex",
            "cursor": "gpt-5.3-codex-high",  # Cursor bakes effort into the id
            "gemini": "gemini-3.6-flash",  # Google-only catalog
            "pi": "openrouter/openai/gpt-5.3-codex:high",
            "omp": "github-copilot/gpt-5.3-codex:high",
        }

        tier_map = ai_models.load_model_tier_map(REPO / "home/.chezmoidata/ai_models.yaml")
        assert set(tier_map) == set(expected), (
            f"harness set changed: {sorted(set(tier_map) ^ set(expected))}; add its gruntwork pick here"
        )
        for harness, model in expected.items():
            row = tier_map[harness]["gruntwork"]
            assert row["model"] == model, (
                f"model_tier_map.{harness}.gruntwork.model is {row['model']!r}, expected {model!r}"
            )
            assert row["effort"] == "high", (
                f"model_tier_map.{harness}.gruntwork.effort is {row['effort']!r}, expected 'high'"
            )

        # Copilot's explore/task subagents are the deployed gruntwork lanes.
        copilot = json.loads((REPO / "home/private_dot_copilot/settings.json").read_text(encoding="utf-8"))[
            "subagents"
        ]["agents"]
        for name in ("explore", "task"):
            assert copilot[name]["model"] == expected["copilot"], (
                f"copilot settings.json {name} model {copilot[name]['model']!r} != {expected['copilot']!r}"
            )
            assert copilot[name]["effortLevel"] == "high", (
                f"copilot settings.json {name} effortLevel is {copilot[name]['effortLevel']!r}, expected 'high'"
            )

    def test_claude_settings_keep_thinking_disabled(self):
        # model_tier_map.claude_code declares thinking "off" for every Anthropic bucket. The only
        # thing enforcing that is alwaysThinkingEnabled: false, which makes Hye() return false so
        # thinkingConfig resolves to {type:"disabled"} instead of {type:"adaptive"}. Dropping it
        # silently turns Opus 5 review lanes back into thinking lanes.
        for profile in ("personal", "work"):
            settings = json.loads((REPO / f"home/dot_claude/settings.{profile}.json").read_text(encoding="utf-8"))
            assert settings.get("alwaysThinkingEnabled") is False, (
                f"claude settings.{profile}.json must set alwaysThinkingEnabled: false, "
                f"got {settings.get('alwaysThinkingEnabled')!r}"
            )
            # CLAUDE_CODE_DISABLE_THINKING defeats the hard disable: the request builder only
            # sends {type:"disabled"} when that env var is absent (`!bn`). It belongs on the
            # non-first-party ,claude-litellm route, never in native settings.
            assert "CLAUDE_CODE_DISABLE_THINKING" not in settings.get("env", {}), (
                f"claude settings.{profile}.json sets CLAUDE_CODE_DISABLE_THINKING, which forces "
                "the omit path and lets adaptive models keep thinking"
            )

    def test_copilot_launcher_disables_anthropic_thinking(self):
        # Opus 5 thinks by default on Copilot. The registry pins Opus for review lanes as the
        # non-thinking pick, which is only true while the launcher exports this env var:
        # app.js Q3e() feeds it to nativeModelClientDefaultOptionsJson, which sets thinkingBudget.
        self.assert_file_contains(
            "home/exact_lib/exact_,copilot/main.py",
            'os.environ.setdefault("COPILOT_DISABLE_ANTHROPIC_THINKING", "1")',
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
            "Run any repo-wide suite, full build, or whole-suite test run **once here**",
            "Lanes deliberately do not load `k-review/SKILL.md`, `shared_rules.md`, `pr_common.md`, `lanes.md`, or a mode file.",
        )
        # Three harnesses can put the router back into a lane through profile frontmatter,
        # each by a different mechanism, so the payload cut has to be asserted per harness.
        # Pi `skills:` injects a name/description/location catalog (pi-subagents
        # src/agents/skills.ts buildSkillInjection) that re-invites the router.
        self.assert_file_not_contains(
            "home/dot_pi/agent/exact_agents/reviewer.md.tmpl",
            "skills: k-review",
        )
        # OMP `autoloadSkills` injects the skill body itself. Check the frontmatter block,
        # not the whole file, so the prose explaining the omission does not trip the assert.
        omp_reviewer = REPO / "home/dot_omp/private_agent/exact_agents/reviewer.md.tmpl"
        omp_frontmatter = omp_reviewer.read_text(encoding="utf-8").split("---")[1]
        assert "autoloadSkills" not in omp_frontmatter, (
            "OMP reviewer frontmatter must not autoload a skill: it injects the skill body, "
            "and k-review would re-add the router that reviewer-worker.md forbids"
        )
        # Claude `skills:` is an allowlist where omitting loads every discovered skill,
        # so it must stay present and stay narrowed to the lens set.
        claude_reviewer = "home/dot_claude/exact_agents/reviewer.md.tmpl"
        self.assert_file_contains(claude_reviewer, "skills:", "  - k-code-quality")
        self.assert_file_not_contains(claude_reviewer, "  - k-review")
        # Every harness lane profile still points at the one shared contract.
        for profile in (
            "home/dot_cursor/exact_agents/readonly_review-worker.md.tmpl",
            "home/dot_codex/exact_agents/readonly_review-worker.toml.tmpl",
            "home/dot_gemini/exact_agents/readonly_review-worker.md.tmpl",
            "home/private_dot_copilot/exact_agents/readonly_review-worker.agent.md.tmpl",
            "home/dot_claude/exact_agents/reviewer.md.tmpl",
            "home/dot_pi/agent/exact_agents/reviewer.md.tmpl",
            "home/dot_omp/private_agent/exact_agents/reviewer.md.tmpl",
        ):
            self.assert_file_contains(profile, "k-review/references/reviewer-worker.md")

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
            "## Cross-family miss sweep (bounded, after the verdicts)",
            "Return at most three, marked `new-candidate`",
            "the controller re-audits them before judgment",
        )
        self.assert_file_not_contains(
            "home/exact_dot_agents/exact_skills/exact_k-review/exact_references/readonly_adversarial-verifier.md",
            "Do not generate new findings; the finder lanes own discovery.",
        )
        # Sweep candidates bypass the audit unless each controller re-audits them inline.
        for controller in (
            "home/exact_dot_agents/exact_skills/exact_k-deep-review/readonly_SKILL.md",
            "home/dot_pi/agent/exact_agents/review-controller.md.tmpl",
            "home/dot_omp/private_agent/exact_agents/review-controller.md.tmpl",
        ):
            self.assert_file_contains(controller, "new-candidate", "Findings-Set Audit")

    def test_live_ui_windows_is_manual_only_and_purged_from_automatic_flows(self):
        # The Windows/VirtualBox environment is a standalone manual-only skill now;
        # `/k-deep-review`, `/k-build`, `live-ui-review`, and `ui-proof` must carry none of its
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
            "home/exact_dot_agents/exact_skills/exact_k-ui-proof/readonly_SKILL.md",
            "windows verification requirement",
            "environments_checked",
        )
        self.assert_file_not_contains(
            "home/exact_dot_agents/exact_skills/exact_k-deep-review/readonly_SKILL.md",
            "Resolve the Windows/VirtualBox verification requirement once",
        )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-deep-review/readonly_SKILL.md",
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
            "Use before a material prose rewrite with several plausible directions",
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

    def test_research_separates_finding_verification_and_deepening(self):
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-research/readonly_SKILL.md",
            "## Multi-source claim branch",
            "A finder never verifies its own claim.",
            "primary-source URL",
            "exact supporting quote",
            "Every numeric literal in the claim must occur verbatim in that quote.",
            "Reject the claim, not the entity or source.",
            "Deepening goes last.",
            "Any new claim from deepening returns to candidate collection and independent verification.",
            "Only verified claims may enter `,ai-kb`",
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
