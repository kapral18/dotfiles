#!/usr/bin/env python3
"""Tests for repository instruction and hook invariants."""

from __future__ import annotations

import ast
import hashlib
import json
import re
import sys
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


SOP_MANIFEST_PATH = "home/dot_config/ai/exact_policy-ir/readonly_policy-manifest.v1.json"


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
            "Deviate from specified procedures only with explicit user approval",
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
            "Build further reasoning only on verified external behavior",
            "label hypotheses explicitly and keep them out of downstream gating",
            "Any locally verifiable assumption or guess must be verified via probes",
            "Resolve material unknowns before proceeding",
            "keep `/tmp` clones for reuse",
            "use local code search (`rg`), file reads, and `git log`",
            "Resolve identity before semantics",
            "For CLIs, resolve the binary path and provenance",
            "For libraries, resolve exact package/version from the lockfile",
            "source config or declaration -> rendered/applied config -> runtime consumer -> minimal safe live probe",
            "Carry investigation, answer, and implementation to completion while required local work remains doable",
            "A summary not verified against full output is a hypothesis, not a fact",
            "human time or perceived effort never justifies skipping verification, simplification, or a locally available probe.",
            "every numeric literal in the claim must occur verbatim in that quote",
            "reject the unverifiable claim, not the source or entity",
        )

    def test_global_sop_keeps_workflow_and_state_machine_gates(self):
        self.assert_file_contains(
            "home/readonly_AGENTS.md",
            "load only that spec",
            "Select exactly one topic",
            "Keep topics broad/stable, avoid topic explosion",
            "conflicts with its target, action, or success and lacks a continuation signal",
            "ask the single most branch-eliminating question",
            "repeat until forks are empty and success criteria are testable",
            "For non-trivial or risky work, make the plan and per-step verification explicit enough to test",
            "Restore alignment before any further speculative change",
            "Reframe tasks into observable checks when practical",
            "bug fixes get reproducing tests",
            "A repo-external `,proof` ledger is a durable receipt, not verification itself",
            "are not ledger triggers by themselves",
            "a ledger created retroactively near the final answer is invalid",
            'invoke `,proof` only on a concrete trigger above, and treat "the task feels non-trivial" as insufficient',
            "repo-external `,proof` ledger",
            "Test-first framing licenses touching only the code the request covers",
            "### 3.4.1 State-Machine Verification",
            "A disposable harness under `/tmp/state-machine-verification/<pwd>/<topic>/<slug>/` is required before that behavior is final or merge-ready.",
            "Reuse an existing harness after reading its manifest and confirming it still matches.",
            "Compare implementation behavior against an independent model/table.",
            "The harness verifies complexity.",
            "Production state machines need an explicit request.",
        )
        self.assert_file_not_contains(
            "home/exact_dot_agents/exact_skills/exact_k-code-quality/readonly_SKILL.md",
            "## State-Machine Verification",
            "Before calling such behavior final or merge-ready",
        )

    def test_skill_namespace_uses_k_prefix(self):
        # Copilot CLI validates the frontmatter `name` (dir name as fallback) and silently
        # drops leading `,`/`_`/`.`/`-`; dir-keyed harnesses (Claude/opencode/pi) use the
        # directory name. The uniform `k-` namespace avoids native-skill collisions in both,
        # so every skill dir and its frontmatter name must carry it.
        skills_root = REPO / "home/exact_dot_agents/exact_skills"
        name_re = re.compile(r"^name: \"?(?P<name>[^\"\n]+)\"?$", re.MULTILINE)
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

    def test_pi_extensions_directory_prunes_unmanaged_drops(self):
        # Pi auto-loads every entry under ~/.pi/agent/extensions and aborts the whole session
        # when one fails to import. A hand-dropped pi-subagents clone with no node_modules did
        # exactly that ("Cannot find module 'yaml'") while the yarn package in `packages` was
        # fine. `exact_` is the guard: chezmoi apply deletes anything not in the source tree.
        managed = REPO / "home/dot_pi/agent/exact_extensions"
        assert managed.is_dir(), (
            "home/dot_pi/agent/exact_extensions must keep the exact_ prefix so chezmoi prunes "
            "unmanaged extension drops instead of letting them break every Pi session"
        )
        assert not (REPO / "home/dot_pi/agent/extensions").exists(), (
            "a non-exact home/dot_pi/agent/extensions directory would stop pruning again"
        )

    def test_proof_access_requires_a_receipt_consumer_or_audit_need(self):
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-proof/readonly_SKILL.md",
            "Use `,proof` only when at least one receipt trigger applies",
            "No other task property is a trigger by itself",
            "checks that are already sufficient inline stay inline rather than being repackaged into a late ledger",
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

    def test_converge_loop_is_manual_only_and_wired_into_sdlc_flows(self):
        # k-converge owns the bounded re-attack loop: a fixed exit condition (a round that
        # changes nothing) plus a correctness-only filter so rounds terminate instead of
        # degenerating into prose churn. It stays manual-only because the model-visible
        # description budget is effectively full; the per-turn hook carries the autonomous nudge.
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-converge/readonly_SKILL.md",
            "disable-model-invocation: true",
            "zero changes to code, tests, or published text",
            "Mutate before you argue",
            "refused, not deferred",
            "no-op revert",
        )
        # The autonomous half: a challenged claim gets a re-verify + converge nudge.
        # Every harness that reimplements the correction directive must carry it, or the
        # nudge silently fires on one harness and not the others.
        for impl in (
            "home/exact_dot_agents/exact_hooks/executable_perturn_recall.py",
            "home/dot_pi/agent/exact_extensions/ai-kb-recall.ts",
            "home/dot_omp/private_agent/extensions/ai-kb-recall.ts",
        ):
            self.assert_file_contains(
                impl,
                "CONVERGE_SIGNALS",
                "unverified-claim",
                "guessed-not-tested",
                "repeat-failure",
                "re-verify it against the artifact",
                "/k-converge",
            )
        # Shared discipline block carries the mechanism for every harness.
        self.assert_file_contains(
            "home/dot_config/exact_tmux/agent_prompts/prefix.txt",
            "Prefer mutation over argument",
            "/k-converge",
        )
        # Every SDLC surface that already runs adversarial work points at the bounded loop.
        # Assert the load-bearing handoff phrase, not the bare token: a passing mention in a
        # comment or changelog line would otherwise satisfy this while the wiring was gone.
        for skill, pointer in (
            ("k-review", "switch to `~/.agents/skills/k-converge/SKILL.md`"),
            ("k-light-review", "hand off to `~/.agents/skills/k-converge/SKILL.md`"),
            ("k-build", "run `~/.agents/skills/k-converge/SKILL.md`"),
        ):
            self.assert_file_contains(
                f"home/exact_dot_agents/exact_skills/exact_{skill}/readonly_SKILL.md",
                pointer,
            )
        # Test-quality and debugging own the mutation/no-op-revert mechanics.
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-code-quality-tests/readonly_SKILL.md",
            "has failed for the right reason",
            "stashes nothing",
        )
        # k-code-quality-tests owns the no-op-revert mechanic; debugging only points at it.
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-diagnosing-bugs/readonly_SKILL.md",
            "revert the fix in place",
        )

    def test_every_wired_hook_command_has_a_chezmoi_source_file(self):
        # A harness config can name `$HOME/.agents/hooks/<x>.py` for a file that was never
        # written: the config parses, the census counts drift, and the hook silently no-ops or
        # errors per harness at runtime. Nothing else in the suite ties the reference to the file,
        # so this walks every config that wires hooks and resolves each command back to its
        # chezmoi source (`exact_hooks/<x>` deploys as `~/.agents/hooks/<x>`, minus the
        # `executable_`/`readonly_` attribute prefixes).
        hooks_dir = REPO / "home/exact_dot_agents/exact_hooks"
        available = set()
        for entry in hooks_dir.iterdir():
            name = entry.name
            for prefix in ("executable_", "readonly_", "private_"):
                name = name.removeprefix(prefix)
            available.add(name.removesuffix(".tmpl"))

        configs = (
            "home/dot_claude/settings.personal.json",
            "home/dot_claude/settings.work.json",
            "home/dot_claude/settings.llama-cpp.json",
            "home/dot_codex/hooks.json.tmpl",
            "home/dot_cursor/hooks.json",
            "home/dot_gemini/settings.json",
        )
        referenced = re.compile(r"\.agents/hooks/([A-Za-z0-9_.-]+\.(?:py|sh))")
        checked = 0
        for config in configs:
            text = (REPO / config).read_text(encoding="utf-8")
            for name in referenced.findall(text):
                checked += 1
                assert name in available, f"{config} wires ~/.agents/hooks/{name}, which has no source in {hooks_dir}"
        assert checked, "no hook references found; the regex or the config list is stale"

    def test_claude_llama_cpp_settings_disable_attribution_header(self):
        settings = json.loads((REPO / "home/dot_claude/settings.llama-cpp.json").read_text(encoding="utf-8"))
        self.assertEqual(settings["env"]["CLAUDE_CODE_ATTRIBUTION_HEADER"], "0")

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
            "CLAUDE_CODE_ATTRIBUTION_HEADER",
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
            "Run `git commit` only when the user explicitly requested a commit in the current conversation",
            "Content approval is not commit authorization",
            "`git pull`, `git pull --rebase`, `git rebase <remote>/<branch>`, or `git merge <remote>/<branch>` before pushing only when the user asks for it",
            "If push is rejected for divergence, non-fast-forward, lease failure, or diverged history, stop and ask how to proceed",
            "Keep configured remote URLs out of output; always redact them",
            "Resolve repository and PR identity with platform metadata (`gh repo view`, `gh pr view`) and list remote names with `git remote`",
            "Redaction is not permission to inspect credential-bearing configuration",
        )
        self.assert_file_contains(
            "home/readonly_AGENTS.md",
            "Run `git commit` only when the user explicitly requested a commit in the current conversation",
            "content approval is not commit authorization",
            "git push --force-with-lease",
            "Push the branch as-is: `git pull`, `git pull --rebase`, `git rebase <remote>/<branch>`, and `git merge <remote>/<branch>` before pushing each require an explicit user request",
            "If push is rejected for divergence, non-fast-forward, lease failure, or diverged history, stop and ask how to proceed",
            "If a human will see the result, draft it, show the exact payload and target, and wait for explicit approval before sending",
            "publish only after that explicit approval, never spontaneously — even to bots",
            "Classify author type from platform API evidence, not display-name heuristics",
            "Classify author type from platform API evidence, not display-name heuristics; evidence, not guessing, decides",
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
            "Handle secrets by reference only: never commit, reveal, or write secrets or plaintext credentials.",
            "Brevity outranks structure. Shortest form that carries the full meaning wins",
            "Structure must earn its space by adding scannable information not present elsewhere",
            "Length is a hard budget per task class, not a vibe",
            "Direct answer or one-shot question: ≤80",
            "Comparison or audit: ≤120",
            "Multi-part investigation: ≤200",
            "Cut words, never facts",
            "One idea per line",
            "You have no valid model of elapsed time, effort, or urgency",
            '"due to time constraints", "for now", "to keep this quick", "that would take a while" are all disqualified',
            'Estimate duration ("~15 minutes", "an afternoon") only when asked',
            "Decide scope on evidence, correctness, risk, and explicit user constraints",
            "Line 1 answers; last line adds new information",
            "Reach for a density primitive before prose",
            "Verdict line",
            "Delta table",
            "Anchor list",
            "Decision block",
            "emit a 1-line skeleton first",
            "Each item appears in exactly one table/list; later sections reference it by name and add only new information",
            "cap at 5",
            "Anchor claims with evidence; keep the verification chain out of the prose and in the anchors",
            "One clarifying question per message",
            "Code citation format: `startLine:endLine:filepath`",
            "In-response result summary only when it carries evidence, outcomes, or next-step constraints",
            "### 6.6 Examples",
            'BAD: "I looked at the file',
            'GOOD: "X. See `file.py:42`."',
            "Pick Claude — only row with drift protection",
            'BAD: "For now, ship this quick fix',
            "Think laterally about root causes and indirect effects",
            "Verify beyond the first plausible explanation before concluding",
            '"Concise" means unpadded, not shallow.',
            "unnecessary churn is a defect, not diligence",
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
        )
        self.assert_file_not_contains(
            "home/readonly_AGENTS.md",
            "### 6.5 External Human Replies",
            "Choose no reply when it would only restate the thread",
        )
        self.assert_file_contains(
            "home/readonly_AGENTS.md",
            "### 2.0 Compatibility Gate",
            "Every implementation summary must include: `Compatibility impact: none | removed (requested) | kept existing (requested)`",
        )
        self.assert_file_contains(
            "home/readonly_AGENTS.md",
            "### 3.5 Delegation Categories",
            "Delegation keeps the conclusion in the caller's context, not the file dumps",
            "Classify by the work, not by the caller",
            "A skill that names a category owns that choice",
            "Capability outranks family diversity every time",
        )
        self.assert_file_contains(
            "home/readonly_AGENTS.md",
            "Recall first with `,ai-kb search` when prior knowledge could help",
            "guesses and session-only notes stay out",
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
            "Load secondary skills only after read/diff evidence proves the surface is in scope.",
            "When invoked for a broad edit, first identify the concrete changed/read files and choose at most the relevant secondary skill(s).",
            "Load React/web/test/design secondaries only for surfaces the evidence already puts in scope, never because they might become relevant later.",
            "Load `~/.agents/skills/k-code-quality-react/SKILL.md` when changed/read files are React, JSX, TSX, hooks, or client-side component state.",
            "Load `~/.agents/skills/k-code-quality-tests/SKILL.md` when changed/read files are tests, fixtures, mocks, assertions, or test plans.",
            "Load `~/.agents/skills/k-code-quality-web/SKILL.md` when changed/read files touch browser-rendered HTML, CSS, layout, visual states, accessibility, or focus behavior.",
            "Load `~/.agents/skills/k-codebase-design/SKILL.md` when the task designs a module interface, decides where a seam goes, or aims to make code more testable.",
            "`as any` and unnecessary type assertions hide real type errors",
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
            "labels-only creation needs explicit approval",
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
            "Use a Conventional Commit header as the PR title only when that exact area has precedent",
        )

    def test_kibana_label_guidance_blocks_esql_label_from_console_mentions(self):
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-kibana-labels-propose/readonly_SKILL.md",
            "this skill is the source of truth for `elastic/kibana` label/backport/version classification",
            "when all changed paths and the linked issue point to Console, propose `Feature:Console`",
            "add `Feature:ES|QL` only when there is separate evidence",
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
            "leave unknown stack/deployment/browser fields blank or marked for follow-up rather than inventing them",
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
            "Accept without rerun a result that reports a valid Playwriter harness blocker:",
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
            "always pass the registry's concrete lane value rather than letting the runtime pick an implicit default",
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
        # The audit narrows the candidate set and the adversarial verifier then refutes only
        # what survived. Reverting to the old parallel/adversarial-first order silently doubles
        # verifier work and lets refuted candidates reach the audit.
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-deep-review/readonly_SKILL.md",
            "5. findings audit, inline or delegated by the findings-audit delegation conditions",
            "6. final adversarial verification (cross-family preferred at equal capability, SOP §3.5) over the audited candidate set",
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
                "## Phase 5 — Final adversarial verification (delegate; cross-family preferred at equal capability, SOP §3.5)",
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

        registry = ai_models.load_agent_review_models(REPO / "home/.chezmoidata/ai_models")
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
        # Copilot review lanes and the cross-family verifier are all pinned at high effort.
        for role in lane_roles + verifier_roles:
            assert agents[role]["effortLevel"] == "high", (
                f"copilot settings.json {role} effortLevel is {agents[role]['effortLevel']!r}, expected 'high'"
            )

    def test_copilot_policy_models_exist_in_the_copilot_catalog(self):
        # When calibrating models, do not assume cross-harness availability. Copilot's effective
        # "available model set" is a captured catalog snapshot (copilot_models); any policy model
        # outside that set is an unverified assumption and must fail fast.
        import ai_models

        registry = REPO / "home/.chezmoidata/ai_models"
        available = {row["id"] for row in ai_models.load_copilot_models(registry)}

        bands = ai_models.load_model_bands(registry)["copilot"]
        review = ai_models.load_agent_review_models(registry)["copilot"]

        used: set[str] = set()
        for band, row in bands.items():
            model = row.get("model")
            if model:
                used.add(model)
            counter = row.get("counter")
            if isinstance(counter, dict) and counter.get("model"):
                used.add(counter["model"])

        for role, model in review.items():
            if model and model != "inherit":
                used.add(model)

        missing = sorted(model for model in used if model not in available)
        assert not missing, f"copilot policy names models not in copilot_models: {missing}"

    def test_review_bands_agree_with_the_review_registry(self):
        # Two registries describe the same review picks: the `max` band (what the hook and the
        # generated rosters enforce) and agent_review_models (what agent profile frontmatter
        # renders). Either can drift into describing a policy the other does not implement.
        import ai_models

        path = REPO / "home/.chezmoidata/ai_models"
        bands = ai_models.load_model_bands(path)
        registry = ai_models.load_agent_review_models(path)
        # model_bands spells the Claude harness claude_code; the review registry spells it claude.
        registry_name = {"claude_code": "claude"}

        for harness, harness_bands in bands.items():
            roles = registry.get(registry_name.get(harness, harness))
            if roles is None:
                continue
            top = harness_bands["max"]
            counter = top.get("counter") or top

            # Claude sessions launch on a deliberately chosen model, so its registry entry is
            # "inherit" and cannot be compared. No other harness may claim that exemption.
            if roles.get("lanes") == "inherit":
                assert harness == "claude_code", (
                    f"{harness} review registry is 'inherit'; only claude_code may be unpinned"
                )
                continue

            assert top["model"] == roles["lanes"], (
                f"model_bands.{harness}.max.model is {top['model']!r} but "
                f"agent_review_models.{registry_name.get(harness, harness)}.lanes is {roles['lanes']!r}"
            )
            if harness == "cursor":
                # Cursor's Task subagents are whitelist-bounded and the policy may intentionally run
                # review + verifier same-family (degraded refutation) by omitting a counter.
                assert roles["verifier"] == roles["lanes"], (
                    f"cursor registry verifier {roles['verifier']!r} != lanes {roles['lanes']!r}"
                )
                continue
            if harness == "omp":
                # Review lanes and verifier both follow @default (same-family per profile).
                # The band carries no counter unless a profile prices advisor as a different family.
                if "counter" in top:
                    assert top["counter"]["model"] == "@advisor", (
                        f"omp max band counter is {top['counter']!r}, expected the @advisor role token"
                    )
                assert roles["verifier"] == roles["lanes"], (
                    f"omp registry verifier {roles['verifier']!r} != lanes {roles['lanes']!r}"
                )
                continue
            assert counter["model"] == roles["verifier"], (
                f"model_bands.{harness}.max counter is {counter['model']!r} but "
                f"agent_review_models.{registry_name.get(harness, harness)}.verifier is {roles['verifier']!r}"
            )

    def test_orchestrate_band_matches_real_harness_config(self):
        # `orchestrate` is the session's own category, and it is the one band that reaches a real
        # config file. Claude Code's is jq-patched into settings.json at apply time and Codex's is
        # a hand-kept literal, so a wrong band ships silently to the session default.
        import ai_models

        path = REPO / "home/.chezmoidata/ai_models"
        categories = ai_models.load_agent_categories(path)
        bands = ai_models.load_model_bands(path)
        orchestrate = categories["orchestrate"]["band"]

        claude_band = bands["claude_code"][orchestrate]
        codex_band = bands["codex"][orchestrate]

        for profile in ("work", "personal"):
            settings = json.loads((REPO / f"home/dot_claude/settings.{profile}.json").read_text(encoding="utf-8"))
            assert settings["model"] == claude_band["model"], (
                f"claude settings.{profile}.json model {settings['model']!r} != "
                f"model_bands.claude_code.{orchestrate}.model {claude_band['model']!r}"
            )
            assert settings["effortLevel"] == claude_band["effort"], (
                f"claude settings.{profile}.json effortLevel {settings['effortLevel']!r} != "
                f"model_bands.claude_code.{orchestrate}.effort {claude_band['effort']!r}"
            )

            config = (REPO / f"home/dot_codex/private_config.{profile}.toml").read_text(encoding="utf-8")
            model = re.search(r'^model\s*=\s*"([^"]+)"', config, re.MULTILINE)
            effort = re.search(r'^model_reasoning_effort\s*=\s*"([^"]+)"', config, re.MULTILINE)
            assert model and model.group(1) == codex_band["model"], (
                f"codex private_config.{profile}.toml model "
                f"{(model.group(1) if model else None)!r} != "
                f"model_bands.codex.{orchestrate}.model {codex_band['model']!r}"
            )
            assert effort and effort.group(1) == codex_band["effort"], (
                f"codex private_config.{profile}.toml model_reasoning_effort "
                f"{(effort.group(1) if effort else None)!r} != "
                f"model_bands.codex.{orchestrate}.effort {codex_band['effort']!r}"
            )

    def test_codex_defaults_and_every_agent_lane_are_sol_xhigh_default(self):
        import ai_models

        registry = REPO / "home/.chezmoidata/ai_models"
        expected_model = "gpt-5.6-sol"
        expected_effort = "xhigh"
        expected_service_tier = "default"

        for band, row in ai_models.load_model_bands(registry)["codex"].items():
            with self.subTest(surface="band", name=band):
                self.assertEqual(row["model"], expected_model)
                self.assertEqual(row["effort"], expected_effort)

        for role, model in ai_models.load_agent_review_models(registry)["codex"].items():
            with self.subTest(surface="review_registry", name=role):
                self.assertEqual(model, expected_model)

        for profile in ("personal", "work"):
            config = (REPO / f"home/dot_codex/private_config.{profile}.toml").read_text(encoding="utf-8")
            with self.subTest(surface="root_profile", name=profile):
                self.assertRegex(config, re.compile(rf'^model\s*=\s*"{re.escape(expected_model)}"$', re.MULTILINE))
                self.assertRegex(
                    config, re.compile(rf'^model_reasoning_effort\s*=\s*"{expected_effort}"$', re.MULTILINE)
                )
                self.assertRegex(config, re.compile(rf'^service_tier\s*=\s*"{expected_service_tier}"$', re.MULTILINE))

        agents = sorted((REPO / "home/dot_codex/exact_agents").glob("*.toml.tmpl"))
        self.assertTrue(agents, "Codex agent profile set is empty")
        for profile in agents:
            config = profile.read_text(encoding="utf-8")
            with self.subTest(surface="agent_profile", name=profile.name):
                self.assertIn(".agent_review_models.codex.", config)
                self.assertRegex(
                    config, re.compile(rf'^model_reasoning_effort\s*=\s*"{expected_effort}"$', re.MULTILINE)
                )
                self.assertRegex(config, re.compile(rf'^service_tier\s*=\s*"{expected_service_tier}"$', re.MULTILINE))

    def test_every_bound_agent_resolves_on_every_harness(self):
        # The three-table lookup is only useful if it is total: an agent bound to a category that
        # a harness cannot price resolves to None, and both the template partial and the hook then
        # fall through to whatever the caller asked for. Silent, and exactly the leak being closed.
        import ai_models

        path = REPO / "home/.chezmoidata/ai_models"
        categories = ai_models.load_agent_categories(path)
        bindings = ai_models.load_agent_bindings(path)
        bands = ai_models.load_model_bands(path)

        for category, spec in categories.items():
            assert spec["family"] in ("primary", "counter"), (
                f"agent_categories.{category}.family is {spec['family']!r}, expected primary or counter"
            )
            for harness, harness_bands in bands.items():
                assert spec["band"] in harness_bands, (
                    f"agent_categories.{category} wants band {spec['band']!r}, "
                    f"which model_bands.{harness} does not define"
                )

        for agent, category in bindings.items():
            assert category in categories, f"agent_bindings.{agent} names unknown category {category!r}"
            for harness in bands:
                pick = ai_models.resolve_agent_model(path, harness, agent)
                assert pick is not None and pick["model"], f"{agent} does not resolve to a model on {harness}"

    def test_the_counter_band_changes_family_or_reports_itself_degraded(self):
        # `refute` exists to break a conclusion, and a refuter from the lanes' own family is worth
        # much less. Where a harness can field a second family it must be a different one; where it
        # cannot, resolution has to say `degraded` so the controller reports the weaker refutation
        # instead of presenting it as a real cross-family pass.
        import ai_models

        path = REPO / "home/.chezmoidata/ai_models"
        bands = ai_models.load_model_bands(path)

        def family(model: str) -> str:
            base = model.rsplit("/", 1)[-1].lstrip("@")
            for name in ("claude", "gpt", "gemini", "grok", "composer", "kimi", "glm"):
                if name in base:
                    return name
            return base

        for harness, harness_bands in bands.items():
            top = harness_bands["max"]
            counter = top.get("counter")
            pick = ai_models.resolve_agent_model(path, harness, "adversarial-verifier")
            if counter is None:
                assert pick["degraded"] is True, (
                    f"model_bands.{harness} has no counter, so refutation must resolve degraded"
                )
                continue
            assert pick["degraded"] is False, f"model_bands.{harness} has a counter but resolution says degraded"
            assert family(top["model"]) != family(counter["model"]), (
                f"model_bands.{harness}.max counter {counter['model']!r} shares a family with {top['model']!r}"
            )

    def test_the_band_gate_only_spawns_for_delegation_tools(self) -> None:
        # band_gate.py no-ops on non-delegation tools, but only after a Python interpreter has
        # spawned and parsed the whole projection. Every wiring must filter before that cost:
        # hooks.json files via a matcher, and the Copilot extension (whose SDK exposes no matcher)
        # via its own copy of DELEGATION_TOOLS, which has to stay in sync with the hook's.
        hook = (REPO / "home/exact_dot_agents/exact_hooks/executable_band_gate.py").read_text(encoding="utf-8")
        tools = re.search(r"^DELEGATION_TOOLS = \{([^}]+)\}", hook, re.MULTILINE)
        assert tools, "band_gate.py no longer declares DELEGATION_TOOLS"
        expected = set(re.findall(r'"([^"]+)"', tools.group(1)))

        extension = (
            REPO / "home/private_dot_copilot/exact_extensions/exact_agent-memory/readonly_extension.mjs"
        ).read_text(encoding="utf-8")
        mirrored = re.search(r"^const DELEGATION_TOOLS = new Set\(\[([^\]]+)\]\)", extension, re.MULTILINE)
        assert mirrored, "the Copilot extension no longer mirrors DELEGATION_TOOLS"
        assert set(re.findall(r'"([^"]+)"', mirrored.group(1))) == expected, (
            "readonly_extension.mjs DELEGATION_TOOLS has drifted from band_gate.py's"
        )
        assert "DELEGATION_TOOLS.has(payload?.tool_name)" in extension, (
            "the Copilot extension spawns band_gate.py without filtering by tool name first"
        )

        for path, key in (
            ("home/dot_cursor/hooks.json", "preToolUse"),
            ("home/dot_claude/settings.personal.json", "PreToolUse"),
            ("home/dot_claude/settings.work.json", "PreToolUse"),
        ):
            settings = json.loads((REPO / path).read_text(encoding="utf-8"))
            entries = settings.get("hooks", {}).get(key, [])
            for entry in entries:
                commands = [entry.get("command", "")] + [h.get("command", "") for h in entry.get("hooks", [])]
                if not any("band_gate.py" in command for command in commands):
                    continue
                assert entry.get("matcher"), f"{path} {key} wires band_gate.py with no matcher"

    def test_the_band_gate_is_wired_on_every_claude_profile(self) -> None:
        # The band gate is the only thing enforcing per-call cost bands on Claude Code, and
        # `chezmoi apply` installs the picked profile whole (07-merge-claude-code-settings patches
        # only .model/.effortLevel). A gate present on one profile and absent on the other means
        # the whole band system is silently unenforced on that machine, and
        # home/dot_config/ai/exact_policy-ir/readonly_harness-capabilities.v1.json claims hook_support="mutation" for both.
        for profile in ("personal", "work"):
            settings = json.loads((REPO / f"home/dot_claude/settings.{profile}.json").read_text(encoding="utf-8"))
            entries = settings.get("hooks", {}).get("PreToolUse", [])
            commands = [
                hook.get("command", "")
                for entry in entries
                for hook in entry.get("hooks", [])
                if entry.get("matcher") == "Agent|Task"
            ]
            assert any("band_gate.py" in command for command in commands), (
                f"claude settings.{profile}.json has no PreToolUse 'Agent|Task' band_gate.py hook, "
                "so delegation bands are unenforced on that profile"
            )

    def test_the_omp_advisor_role_is_not_sold_as_a_second_family(self) -> None:
        # OMP names roles, not models, so a `counter: "@advisor"` band would be a cross-family
        # claim that only readonly_config.yml.tmpl can settle. A counter is required as soon as
        # ANY profile resolves `advisor` to a different id than `default`; profiles that keep
        # advisor == default resolve refutation same-family at runtime (reduced independence).
        import ai_models

        path = REPO / "home/.chezmoidata/ai_models"
        counter = ai_models.load_model_bands(path)["omp"]["max"].get("counter")
        roles = self._omp_model_roles()

        assert set(roles) == {"work", "personal"}, f"unexpected OMP profiles {sorted(roles)}"
        any_distinct = any(mapping["advisor"] != mapping["default"] for mapping in roles.values())
        if any_distinct:
            assert counter is not None, (
                "omp modelRoles has a distinct advisor on at least one profile "
                f"({roles!r}); model_bands.omp.max must carry the counter so refutation "
                "stops reporting degraded there"
            )
        else:
            assert counter is None, (
                f"omp modelRoles resolves advisor to the lanes' own model on every profile "
                f"({roles!r}), so model_bands.omp.max must carry no counter"
            )

    @staticmethod
    def _omp_model_roles() -> dict[str, dict[str, str]]:
        """Parse the per-profile `modelRoles` blocks out of OMP's config template."""
        source = (REPO / "home/dot_omp/private_agent/readonly_config.yml.tmpl").read_text(encoding="utf-8")
        profiles: dict[str, dict[str, str]] = {}
        current: dict[str, str] | None = None
        profile = "work"  # the template opens on `{{ if eq .isWork true }}`
        for line in source.splitlines():
            if ".isWork" in line:
                profile = "work"
                continue
            if line.strip() in ("# {{ else }}", "{{ else }}"):
                profile = "personal"
                continue
            if line.startswith("modelRoles:"):
                current = {}
                profiles[profile] = current
                continue
            if current is None:
                continue
            match = re.match(r"^  ([\w-]+):\s*(\S+)\s*$", line)
            if match:
                current[match.group(1)] = match.group(2)
            elif line.strip() and not line.startswith("  "):
                current = None
        assert profiles, "no modelRoles block found in OMP's config template"
        return profiles

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

        bands = ai_models.load_model_bands(REPO / "home/.chezmoidata/ai_models")
        for band, row in bands["claude_code"].items():
            check(f"model_bands.claude_code.{band}", row.get("model", ""))

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

        bands = ai_models.load_model_bands(REPO / "home/.chezmoidata/ai_models")
        for harness, harness_bands in bands.items():
            for band, row in harness_bands.items():
                check(f"model_bands.{harness}.{band}", row.get("model", ""), row.get("effort"))
                counter = row.get("counter")
                if isinstance(counter, dict):
                    check(
                        f"model_bands.{harness}.{band}.counter",
                        counter.get("model", ""),
                        counter.get("effort"),
                    )

        registry = ai_models.load_agent_review_models(REPO / "home/.chezmoidata/ai_models")
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
            model = re.search(r'^model\s*=\s*"([^"]+)"', codex, re.MULTILINE)
            effort = re.search(r'^model_reasoning_effort\s*=\s*"([^"]+)"', codex, re.MULTILINE)
            if model:
                check(
                    f"codex private_config.{profile}.toml",
                    model.group(1),
                    effort.group(1) if effort else None,
                )

        assert not offenders, "gpt-5.5 must always run at high effort:\n  " + "\n  ".join(offenders)

    def test_bands_are_short_context_by_default(self):
        # Standing policy: short context everywhere. `long` is allowed only where the harness
        # publishes no short variant of the wanted model, which today is Cursor alone — it ships
        # Opus 5, Sonnet 5, Fable 5 and the GPT-5.x ids exclusively as 1M ids. Any other `long` row is
        # drift, and an empty value is worse: it reads as "nobody decided" and hides the window.
        import ai_models

        cursor_1m_only = (
            "claude-opus-5",
            "claude-sonnet-5",
            "claude-fable-5",
            "gpt-5.5",
            "gpt-5.6-sol",
            "gpt-5.6-terra",
        )
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

        bands = ai_models.load_model_bands(REPO / "home/.chezmoidata/ai_models")
        for harness, harness_bands in bands.items():
            for band, row in harness_bands.items():
                check(f"model_bands.{harness}.{band}", harness, row.get("model", ""), row.get("context"))
                counter = row.get("counter")
                if isinstance(counter, dict):
                    check(
                        f"model_bands.{harness}.{band}.counter",
                        harness,
                        counter.get("model", ""),
                        counter.get("context"),
                    )

        # Copilot's contextTier is the only dial that turns the policy into a runtime request.
        copilot = json.loads((REPO / "home/private_dot_copilot/settings.json").read_text(encoding="utf-8"))
        for name, agent in copilot["subagents"]["agents"].items():
            tier = agent.get("contextTier")
            if tier != "default":
                offenders.append(f"copilot settings.json {name}: contextTier is {tier!r}, expected 'default'")

        # `[1m]` is the Claude Code selector that swaps a bare id onto a provider's 1M window.
        for relative in (
            "home/exact_bin/executable_,claude-openrouter",
            "home/dot_config/fish/readonly_config.fish.tmpl",
        ):
            source = (REPO / relative).read_text(encoding="utf-8")
            code = "\n".join(line for line in source.splitlines() if not line.lstrip().startswith("#"))
            if "[1m]" in code:
                offenders.append(f"{relative}: carries a [1m] extended-context selector")

        assert not offenders, "short context is the default everywhere:\n  " + "\n  ".join(offenders)

    def test_openrouter_routes_are_a_strict_route(self):
        import ai_models
        import model_mirrors

        default = "deepseek/deepseek-v4-flash-0731"
        optional = "moonshotai/kimi-k3"
        glm = "z-ai/glm-5.2"
        counter = "openai/gpt-5.6-terra"
        default_selector = f"openrouter/{default}"
        optional_selector = f"openrouter/{optional}"
        glm_selector = f"openrouter/{glm}"
        counter_selector = f"openrouter/{counter}"
        expected_default_provider_routing = {
            "sort": "price",
            "quantizations": ["fp8", "fp16", "bf16", "fp32"],
            "preferred_min_throughput": 24,
        }
        expected_glm_provider_routing = {
            "sort": "price",
            "quantizations": ["fp8", "fp16", "bf16", "fp32"],
            "preferred_min_throughput": 24,
        }
        expected_optional_provider_routing = {
            "only": ["fireworks", "together", "baseten"],
            "allow_fallbacks": False,
            "sort": "throughput",
            "max_price": {"completion": 16},
        }
        registry = REPO / "home/.chezmoidata/ai_models"
        provider_models = [
            row["id"] for row in ai_models.load_provider_models(registry) if row["provider"] == "openrouter"
        ]
        # DeepSeek max carries every default lane; Kimi and GLM-5.2 stay selectable and Terra carries counter roles.
        self.assertEqual([default, optional, glm, counter], provider_models)
        self.assertEqual(
            [
                {"id": default_selector, "recommended": True},
                {"id": optional_selector},
                {"id": glm_selector},
                {"id": counter_selector},
            ],
            ai_models.load_pi_extra_models(registry),
        )

        for profile in ("work", "personal"):
            settings = json.loads((REPO / f"home/dot_pi/agent/readonly_settings.{profile}.json").read_text())
            self.assertEqual("openrouter", settings["defaultProvider"])
            self.assertEqual(default, settings["defaultModel"])
            self.assertEqual("max", settings["defaultThinkingLevel"])

            pi_models = json.loads(
                (
                    REPO / f"home/dot_pi/agent/readonly_models{'.personal' if profile == 'personal' else ''}.json"
                ).read_text()
            )
            pi_overrides = pi_models["providers"]["openrouter"]["modelOverrides"]
            default_compat = pi_overrides[default]["compat"]
            optional_compat = pi_overrides[optional]["compat"]
            glm_compat = pi_overrides[glm]["compat"]
            self.assertEqual(expected_default_provider_routing, default_compat["openRouterRouting"])
            self.assertEqual(expected_optional_provider_routing, optional_compat["openRouterRouting"])
            self.assertEqual(expected_glm_provider_routing, glm_compat["openRouterRouting"])
            self.assertNotIn("extraBody", default_compat)
            self.assertNotIn("extraBody", optional_compat)
            self.assertNotIn("extraBody", glm_compat)

            opencode = model_mirrors._read_jsonc(REPO / f"home/dot_config/opencode/readonly_opencode.{profile}.jsonc")
            default_preset = f"{default}@preset/deepseek-lanes-max"
            optional_preset = f"{optional}@preset/kimi-lanes"
            glm_preset = f"{glm}@preset/glm-lanes-max"
            self.assertEqual(f"openrouter/{default_preset}", opencode["small_model"])
            # OpenCode cannot inject the `provider` routing body field, so both routes carry
            # their provider policies through workspace presets.
            for name, agent in opencode["agent"].items():
                if isinstance(agent, dict) and agent.get("model", "").startswith("openrouter/"):
                    self.assertEqual(f"openrouter/{default_preset}", agent["model"], name)
                    self.assertEqual("max", agent["reasoning_effort"], name)
            openrouter_models = opencode["provider"]["openrouter"]["models"]
            self.assertEqual("max", openrouter_models[default_preset]["options"]["reasoningEffort"])
            self.assertEqual("high", openrouter_models[optional_preset]["options"]["reasoningEffort"])
            self.assertEqual("max", openrouter_models[glm_preset]["options"]["reasoningEffort"])
            self.assertNotIn(default, openrouter_models)
            self.assertNotIn(optional, openrouter_models)
            self.assertNotIn(glm, openrouter_models)
            self.assertNotIn(counter, openrouter_models)

        review = ai_models.load_agent_review_models(registry)["pi"]
        self.assertEqual(f"{default_selector}:max", review["lanes"])
        self.assertEqual(f"{counter_selector}:max", review["verifier"])
        bands = ai_models.load_model_bands(registry)["pi"]
        self.assertEqual(f"{default_selector}:max", bands["cheap"]["model"])
        self.assertEqual("max", bands["cheap"]["effort"])
        for band in ("standard", "max"):
            self.assertEqual(f"{default_selector}:max", bands[band]["model"], band)
            self.assertEqual("max", bands[band]["effort"], band)
        self.assertEqual(f"{counter_selector}:max", bands["max"]["counter"]["model"])

        for relative in (
            "home/exact_bin/executable_,claude-openrouter",
            "home/exact_bin/executable_,codex-openrouter",
            "home/exact_bin/executable_,copilot-openrouter",
            "home/exact_bin/executable_,cursor-openrouter",
        ):
            source = (REPO / relative).read_text()
            # Default route is DeepSeek max; model/effort flags still compose other preset slugs.
            self.assertIn(f'OPENROUTER_MODEL="{default}"', source)
            self.assertIn('OPENROUTER_EFFORT="max"', source)

        omp = (REPO / "home/dot_omp/private_agent/readonly_config.yml.tmpl").read_text()
        # OMP's work-profile modelRoles route through OpenRouter (user call 2026-08-06); the
        # provider order must keep listing it for both profiles.
        self.assertIn("  - openrouter\n", omp)
        omp_models = (REPO / "home/dot_omp/private_agent/readonly_models.yml").read_text()
        # OMP 17.2.9 does not put modelOverrides…compat.extraBody.provider on the wire, so the
        # provider policy rides the OpenRouter preset slug instead (same as the wrappers/OpenCode).
        self.assertIn(
            '      - id: "deepseek/deepseek-v4-flash-0731@preset/deepseek-lanes-max"\n',
            omp_models,
        )
        self.assertIn(
            '      - id: "moonshotai/kimi-k3@preset/kimi-lanes"\n',
            omp_models,
        )
        # No per-request extraBody/modelOverrides routing (the typed wire would drop it) and no
        # stray openRouterRouting config key.
        self.assertNotIn("extraBody:", omp_models)
        self.assertNotIn("modelOverrides:", omp_models)
        self.assertNotIn("openRouterRouting", omp_models)

    def test_neovim_openrouter_summarizer_pins_gpt_oss_120b(self):
        # Personal leader-aisc talks to OpenRouter directly. gpt-oss-120b is not on the DeepSeek
        # wrapper route. OpenRouter's catalog lists supported_efforts high/medium/low. Provider
        # routing is price-sorted with a 300 t/s preferred floor (OpenRouter deprioritizes slower
        # endpoints; it does not hard-exclude them). Output cap is the endpoint max completion
        # (131072), not a 2048-token ceiling. Not a Cerebras-only whitelist.
        neovim = (
            REPO / "home/dot_config/exact_nvim/exact_lua/exact_plugins_local_src/readonly_summarize-commit.lua"
        ).read_text()
        self.assertIn('local OPENROUTER_DEFAULT_MODEL = "openai/gpt-oss-120b"', neovim)
        self.assertNotIn('local OPENROUTER_DEFAULT_MODEL = "deepseek/deepseek-v4-flash-0731"', neovim)
        self.assertIn("local OPENROUTER_MAX_OUTPUT_TOKENS = 131072", neovim)
        self.assertIn("max_tokens = OPENROUTER_MAX_OUTPUT_TOKENS,", neovim)
        self.assertNotIn("local DEFAULT_MAX_OUTPUT_TOKENS = 2048", neovim)
        self.assertNotIn("DIFF_SIZE_LIMIT", neovim)
        self.assertIn("local GEMINI_DEFAULT_MAX_OUTPUT_TOKENS = 65536", neovim)
        self.assertIn("or GEMINI_DEFAULT_MAX_OUTPUT_TOKENS", neovim)
        self.assertIn('reasoning = { effort = "high" }', neovim)
        self.assertNotIn('reasoning = { effort = "max" }', neovim)
        self.assertIn(
            'local OPENROUTER_PROVIDER_ROUTING = { sort = "price", preferred_min_throughput = 300 }',
            neovim,
        )
        self.assertIn("provider = OPENROUTER_PROVIDER_ROUTING,", neovim)
        self.assertNotIn('only = { "cerebras" }', neovim)
        self.assertNotIn("quantizations", neovim)
        self.assertNotIn("fireworks", neovim)
        for variable in ("OPENROUTER_MODEL", "OPENROUTER_NITRO", "OPENROUTER_THINKING", "OPENROUTER_REASONING_EFFORT"):
            self.assertNotIn(variable, neovim)

    def test_the_cheap_band_runs_the_codex_tier_wherever_the_catalog_has_it(self):
        # `cheap` carries judgment-free `search` and `mechanical` work, so it takes gpt-5.3-codex at
        # high effort on every harness whose catalog has it. Five cannot: Claude Code and Gemini are
        # single-vendor, native Codex deliberately pins Sol/xhigh across every band, Cursor's Task
        # tool takes only its own whitelist (user call 2026-08-14 pins every Cursor band to
        # cursor-grok-4.6-xhigh), and Pi reaches models only through OpenRouter, where the cheap
        # role is pinned to deepseek-v4-flash-0731:max. Each exception is spelled out so a future
        # edit cannot quietly downgrade a harness that could have run the codex tier.
        import ai_models

        expected = {
            "claude_code": ("claude-fable-5", "low"),  # Anthropic-only; all bands fable-5 (user call 2026-08-05)
            "codex": ("gpt-5.6-sol", "xhigh"),  # user-selected all-band Codex policy
            "copilot": ("claude-haiku-4.5", "high"),
            "cursor": ("cursor-grok-4.6-xhigh", "xhigh"),  # all-band Cursor pin (user call 2026-08-14)
            "gemini": ("gemini-3.6-flash", "high"),  # Google-only catalog
            "pi": ("openrouter/deepseek/deepseek-v4-flash-0731:max", "max"),  # OpenRouter-only; cheap role route
            "omp": ("@smol", "high"),  # a role token; the concrete pick is asserted below
        }

        path = REPO / "home/.chezmoidata/ai_models"
        bands = ai_models.load_model_bands(path)
        assert set(bands) == set(expected), (
            f"harness set changed: {sorted(set(bands) ^ set(expected))}; add its cheap-band pick here"
        )
        for harness, (model, effort) in expected.items():
            row = bands[harness]["cheap"]
            assert row["model"] == model, f"model_bands.{harness}.cheap.model is {row['model']!r}, expected {model!r}"
            assert row["effort"] == effort, (
                f"model_bands.{harness}.cheap.effort is {row['effort']!r}, expected {effort!r}"
            )

        # `composer-2.5-fast` is a speed tier with the same intelligence at 6x the price
        # ($3/$15 against $0.5/$2.5, cursor.com/docs/models), so no band may reach for it.
        for band, row in bands["cursor"].items():
            assert row["model"] != "composer-2.5-fast", (
                f"model_bands.cursor.{band} is composer-2.5-fast; composer-2.5 is the same model for a sixth"
            )

        # OMP resolves its bands through modelRoles; @smol is deliberately composer-2.5 on personal
        # (policy override), even though a codex-tier id is available in the catalog. Work routes
        # smol through the OpenRouter deepseek deepseek-lanes-max preset (FP8-or-higher, throughput-
        # sorted; qwen3.8-max and minimax-m3 rejected, user call 2026-08-06).
        roles = self._omp_model_roles()
        assert "openrouter/deepseek/deepseek-v4-flash-0731@preset/deepseek-lanes-max" in roles["work"]["smol"], (
            f"omp work modelRoles.smol is {roles['work']['smol']!r}, expected openrouter/deepseek/deepseek-v4-flash-0731@preset/deepseek-lanes-max"
        )
        assert "composer-2.5" in roles["personal"]["smol"], (
            f"omp personal modelRoles.smol is {roles['personal']['smol']!r}, expected composer-2.5"
        )

        # Copilot is the one harness where the cheap band reaches a deployed file rather than a
        # rendered profile, so check the band actually landed on every cheap-bound built-in.
        #
        # Copilot may legitimately have none: `search` narrowed to judgment-free work only (see the
        # investigation note in tiering.yaml agent_bindings), and Copilot ships no such built-in —
        # `explore` forms conclusions, so it is `research`. An empty set means the cheap band is
        # simply unreachable on this harness, not that a pin was dropped, so the loop below is a
        # no-op rather than a failure. If a cheap-bound Copilot agent is ever added, it is checked.
        bindings = ai_models.load_agent_bindings(path)
        categories = ai_models.load_agent_categories(path)
        copilot = json.loads((REPO / "home/private_dot_copilot/settings.json").read_text(encoding="utf-8"))[
            "subagents"
        ]["agents"]
        cheap_agents = [name for name in copilot if categories.get(bindings.get(name, ""), {}).get("band") == "cheap"]
        copilot_model, copilot_effort = expected["copilot"]
        for name in cheap_agents:
            assert copilot[name]["model"] == copilot_model, (
                f"copilot settings.json {name} model {copilot[name]['model']!r} != {copilot_model!r}"
            )
            assert copilot[name]["effortLevel"] == copilot_effort, (
                f"copilot settings.json {name} effortLevel is {copilot[name]['effortLevel']!r}, expected {copilot_effort!r}"
            )

    def test_generated_subagent_rosters_match_the_band_registry(self):
        # Copilot's settings.json and Gemini's agents.overrides both pin subagent models inside a
        # file the harness rewrites at runtime, so neither can be a chezmoi template over the
        # registry: scripts/generate_subagent_models.py reconciles them instead. Copilot's has
        # drifted before, and Gemini's was unguarded entirely.
        import subprocess

        result = subprocess.run(
            [sys.executable, str(REPO / "scripts/generate_subagent_models.py"), "check"],
            capture_output=True,
            text=True,
            cwd=str(REPO),
        )
        assert result.returncode == 0, (
            "Copilot/Gemini subagent rosters diverge from model_bands; run "
            f"`python3 scripts/generate_subagent_models.py write`:\n{result.stderr}"
        )

    def test_the_deployed_band_projection_is_current(self):
        # The hook runs from ~/.agents/hooks with no access to this repo, so it reads a flattened
        # projection instead of resolving anything. A stale projection is a silently wrong model on
        # every harness the hook enforces.
        import subprocess

        result = subprocess.run(
            [sys.executable, str(REPO / "scripts/generate_agent_bands.py"), "check"],
            capture_output=True,
            text=True,
            cwd=str(REPO),
        )
        assert result.returncode == 0, result.stderr

    def test_cursor_bands_stay_inside_the_task_tool_whitelist(self):
        # Cursor IDE Task enum 2026-08-14 (this session): a far narrower list than
        # `cursor-agent models`. Anything else fails the spawn with "Invalid model
        # selection". Since Cursor has no loadable agent files, the band hook is the only tiering
        # surface there, and a slug outside this list breaks delegation rather than repricing it.
        import ai_models

        whitelist = {
            "claude-fable-5-medium",
            "claude-opus-5-high",
            "claude-sonnet-5-thinking-max",
            "composer-2.5",
            "composer-2.5-fast",
            "cursor-grok-4.5-high-fast",
            "cursor-grok-4.6-xhigh",
            "gpt-5.6-sol-xhigh",
            "gpt-5.6-terra-xhigh",
        }

        bands = ai_models.load_model_bands(REPO / "home/.chezmoidata/ai_models")["cursor"]
        for band, row in bands.items():
            for label, pick in (("", row), (".counter", row.get("counter") or {})):
                model = pick.get("model")
                if not model:
                    continue
                assert model in whitelist, (
                    f"model_bands.cursor.{band}{label} is {model!r}, which the Task tool cannot resolve; "
                    f"pick one of {sorted(whitelist)}"
                )

    def test_claude_settings_keep_thinking_disabled(self):
        # model_bands.claude_code declares thinking "off" for every Anthropic bucket. The only
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
            # non-first-party ,claude-openrouter route, never in native settings.
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
            "Load only the files above; `k-review/SKILL.md`, `shared_rules.md`, `pr_common.md`, `lanes.md`, and mode files stay unloaded.",
            "Leave repo-wide suites, full builds, and whole-suite test runs to the controller.",
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
            "## Miss sweep (bounded, after the verdicts)",
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
            "## Manual only — explicit request required",
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
