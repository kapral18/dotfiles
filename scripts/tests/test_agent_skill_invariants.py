#!/usr/bin/env python3
"""Focused tests for agent instruction invariants."""

from __future__ import annotations

import json
import re
import sys
import unittest

import _test_support  # noqa: F401  (puts scripts/ on sys.path)
from _test_support import REPO


class TestAgentSkillInvariants(unittest.TestCase):
    def assert_file_contains(self, relative_path: str, *snippets: str) -> None:
        text = (REPO / relative_path).read_text(encoding="utf-8")
        for snippet in snippets:
            assert snippet in text, f"{relative_path} is missing instruction: {snippet}"

    def assert_file_not_contains(self, relative_path: str, *snippets: str) -> None:
        text = (REPO / relative_path).read_text(encoding="utf-8")
        for snippet in snippets:
            assert snippet not in text, f"{relative_path} should not contain: {snippet}"

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
            "home/dot_gemini/config/readonly_hooks.json",
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
            "Do not use a Conventional Commit header as the PR title unless that exact area has precedent",
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
