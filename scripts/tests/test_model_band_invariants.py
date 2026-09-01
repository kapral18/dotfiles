#!/usr/bin/env python3
"""Focused tests for agent instruction invariants."""

from __future__ import annotations

import json
import re
import sys
import unittest

import _test_support  # noqa: F401  (puts scripts/ on sys.path)
from _test_support import REPO


class TestModelBandInvariants(unittest.TestCase):
    def assert_file_contains(self, relative_path: str, *snippets: str) -> None:
        text = (REPO / relative_path).read_text(encoding="utf-8")
        for snippet in snippets:
            assert snippet in text, f"{relative_path} is missing instruction: {snippet}"

    def assert_file_not_contains(self, relative_path: str, *snippets: str) -> None:
        text = (REPO / relative_path).read_text(encoding="utf-8")
        for snippet in snippets:
            assert snippet not in text, f"{relative_path} should not contain: {snippet}"

    def test_copilot_subagent_settings_match_the_review_model_resolver(self):
        # Copilot resolves subagent models from ~/.copilot/settings.json, which a merge script
        # reads as source JSON, so it cannot be a chezmoi template. The expected picks come from
        # the same review resolver profile templates use.
        import ai_models

        registry = REPO / "home/.chezmoidata/ai_models"
        agents = json.loads((REPO / "home/private_dot_copilot/settings.json").read_text(encoding="utf-8"))["subagents"][
            "agents"
        ]

        review_roles = (
            "deep-review",
            "review-worker",
            "review-worker-cross",
            "findings-auditor",
            "pr-necessity-auditor",
            "live-ui-review",
            "adversarial-verifier",
            "criteria-verifier",
        )
        for role in review_roles:
            expected = ai_models.resolve_review_agent_model(registry, "copilot", role)
            assert expected is not None, f"{role} has no resolved review model"
            assert agents[role]["model"] == expected["model"], (
                f"copilot settings.json {role} model {agents[role]['model']!r} != "
                f"resolved review model {expected['model']!r}"
            )
            assert agents[role]["effortLevel"] == expected["effort"], (
                f"copilot settings.json {role} effortLevel is {agents[role]['effortLevel']!r}, "
                f"expected {expected['effort']!r}"
            )

    def test_copilot_policy_models_exist_in_the_copilot_catalog(self):
        # When calibrating models, do not assume cross-harness availability. Copilot's effective
        # "available model set" is a captured catalog snapshot (copilot_models); any policy model
        # outside that set is an unverified assumption and must fail fast.
        import ai_models

        registry = REPO / "home/.chezmoidata/ai_models"
        available = {row["id"] for row in ai_models.load_copilot_models(registry)}

        category_models = ai_models.load_category_models(registry)["copilot"]
        review_roles = (
            "deep-review",
            "review-worker",
            "review-worker-cross",
            "findings-auditor",
            "pr-necessity-auditor",
            "live-ui-review",
            "adversarial-verifier",
            "criteria-verifier",
        )

        used: set[str] = set()
        for category, row in category_models.items():
            model = row.get("model")
            if model:
                used.add(model)

        for role in review_roles:
            pick = ai_models.resolve_review_agent_model(registry, "copilot", role)
            if pick and pick["model"] and pick["model"] != "inherit":
                used.add(pick["model"])

        missing = sorted(model for model in used if model not in available)
        assert not missing, f"copilot policy names models not in copilot_models: {missing}"

    def test_copilot_category_matrix_uses_gpt55_with_requested_exceptions(self):
        import ai_models

        rows = ai_models.load_category_models(REPO / "home/.chezmoidata/ai_models")["copilot"]
        settings = json.loads((REPO / "home/private_dot_copilot/settings.json").read_text(encoding="utf-8"))

        for category in ("lookup", "research", "implement", "orchestrate", "review"):
            with self.subTest(category=category):
                self.assertEqual("gpt-5.5", rows[category]["model"])
                self.assertEqual("xhigh", rows[category]["effort"])
        self.assertEqual("gpt-5.5", settings["model"])
        self.assertEqual("xhigh", settings["effortLevel"])
        self.assertEqual("claude-sonnet-4.6", rows["mechanical"]["model"])
        self.assertEqual("high", rows["mechanical"]["effort"])
        self.assertEqual("claude-fable-5.1", rows["refute"]["model"])
        self.assertEqual("high", rows["refute"]["effort"])
        self.assertEqual("cross_family", rows["refute"]["verifier_status"])
        self.assertEqual("claude-sonnet-4.6", rows["memory"]["model"])
        self.assertEqual("high", rows["memory"]["effort"])
        self.assertEqual("short", rows["memory"]["context"])

    def test_cursor_category_matrix_uses_task_enum_models_with_requested_exceptions(self):
        import ai_models

        rows = ai_models.load_category_models(REPO / "home/.chezmoidata/ai_models")["cursor"]

        for category in ("lookup", "research", "implement", "orchestrate", "review"):
            with self.subTest(category=category):
                self.assertEqual("gpt-5.6-sol-high", rows[category]["model"])
                self.assertEqual("high", rows[category]["effort"])
                self.assertEqual("long", rows[category]["context"])
        # Cheap lanes use the `auto` router selector (user call 2026-08-30): Cursor picks the
        # small model itself. Live-verified 2026-08-30 (cursor-agent 2026.08.28-a7f9513): a Task
        # spawn with an explicit model "auto" was accepted (caller models are validated before
        # hook rewrites, so the probe hit the real enum), and interactive `cursor-agent --model
        # auto` completed a full turn.
        self.assertEqual("auto", rows["mechanical"]["model"])
        self.assertEqual("", rows["mechanical"]["effort"])
        self.assertEqual("short", rows["mechanical"]["context"])
        self.assertEqual("claude-opus-5-high", rows["refute"]["model"])
        self.assertEqual("high", rows["refute"]["effort"])
        self.assertEqual("long", rows["refute"]["context"])
        self.assertEqual("cross_family", rows["refute"]["verifier_status"])
        # memory (smol) rides the same `auto` router pick.
        self.assertEqual("auto", rows["memory"]["model"])
        self.assertEqual("short", rows["memory"]["context"])

    def test_gemini_category_matrix_uses_pro_with_flash_mechanical_long_context(self):
        import ai_models

        rows = ai_models.load_category_models(REPO / "home/.chezmoidata/ai_models")["gemini"]

        for category in ("lookup", "research", "implement", "orchestrate", "review", "refute"):
            with self.subTest(category=category):
                self.assertEqual("gemini-3.1-pro-preview", rows[category]["model"])
                self.assertEqual("high", rows[category]["effort"])
                self.assertEqual("long", rows[category]["context"])
        self.assertEqual("gemini-3.7-flash", rows["mechanical"]["model"])
        self.assertEqual("high", rows["mechanical"]["effort"])
        self.assertEqual("long", rows["mechanical"]["context"])
        self.assertEqual("gemini-3.7-flash", rows["memory"]["model"])
        self.assertEqual("degraded", rows["refute"]["verifier_status"])

    def test_memory_category_binds_smol_and_projects_into_the_deployed_bands(self):
        # smol is the ,ai-kb operator: every harness must resolve it through the memory
        # category, and the deployed band projection must pin the same pick so the band
        # gate clamps delegated smol calls.
        import ai_models

        registry = REPO / "home/.chezmoidata/ai_models"
        assert ai_models.load_agent_bindings(registry)["smol"] == "memory"
        category_models = ai_models.load_category_models(registry)
        bands = json.loads((REPO / "home/dot_config/ai/readonly_agent-bands.v1.json").read_text(encoding="utf-8"))
        for harness, rows in category_models.items():
            with self.subTest(harness=harness):
                pick = ai_models.resolve_agent_model(registry, harness, "smol")
                self.assertEqual(rows["memory"]["model"], pick["model"])
                self.assertEqual(rows["memory"]["model"], bands["harnesses"][harness]["agents"]["smol"]["model"])

    def test_review_model_resolver_uses_category_models_except_declared_overrides(self):
        # Review routing has one source rule: override only for harness selectors that
        # category_models cannot express, otherwise derive lane/verifier picks from the direct
        # category row.
        import ai_models

        path = REPO / "home/.chezmoidata/ai_models"
        category_models = ai_models.load_category_models(path)
        overrides = ai_models.load_review_model_overrides(path)
        # Sparse by contract: claude/gemini override the lanes/verifier slots; copilot/cursor only
        # declare the cross-family aux slot (lanes_cross) and fall back to the category pick for
        # everything else. Single-vendor catalogs (claude_code, codex) declare nothing.
        expected_overrides = {"claude", "gemini", "copilot", "cursor"}
        assert set(overrides) == expected_overrides, (
            f"review_model_overrides should stay sparse; unexpected keys {sorted(set(overrides) ^ expected_overrides)}"
        )
        assert set(overrides["copilot"]) == {"lanes_cross"}
        assert set(overrides["cursor"]) == {"lanes_cross"}

        review_agents = ("reviewer", "deep-review", "findings-auditor", "live-ui-review", "adversarial-verifier")
        review_harnesses = {
            "claude_code": "claude",
            **{harness: harness for harness in category_models if harness != "claude_code"},
        }
        for band_harness, review_harness in review_harnesses.items():
            for agent in review_agents:
                pick = ai_models.resolve_review_agent_model(path, review_harness, agent)
                assert pick is not None, f"{agent} does not resolve on {review_harness}"
                if pick["slot"] in overrides.get(review_harness, {}):
                    assert pick["source"] == "override"
                    assert pick["model"] == overrides[review_harness][pick["slot"]]
                    continue

                category = "refute" if pick["slot"] == "verifier" else pick["category"]
                expected_row = category_models[band_harness][category]
                assert pick["source"] == "category_models"
                assert pick["model"] == expected_row["model"], (
                    f"{review_harness} {agent} resolved {pick['model']!r}, "
                    f"expected {expected_row['model']!r} from category_models"
                )
                if pick["slot"] == "verifier" and expected_row.get("verifier_status") == "reduced_independence":
                    assert pick["verifier_status"] == "reduced_independence"
                    assert pick["degraded"] is False

        # The cross-family finder lane resolves through the lanes_cross aux slot where declared,
        # and degrades to the standard lane model on single-vendor harnesses (template parity).
        cross_expected = {"copilot": overrides["copilot"]["lanes_cross"], "cursor": overrides["cursor"]["lanes_cross"]}
        for review_harness, model in cross_expected.items():
            pick = ai_models.resolve_review_agent_model(path, review_harness, "review-worker-cross")
            assert pick is not None, f"review-worker-cross does not resolve on {review_harness}"
            assert pick["source"] == "override"
            assert pick["model"] == model
            assert "effort" in pick, "override picks merge the category row underneath"
        for review_harness in ("claude", "codex"):
            pick = ai_models.resolve_review_agent_model(path, review_harness, "review-worker-cross")
            assert pick is not None, f"review-worker-cross does not resolve on {review_harness}"
            lane = ai_models.resolve_review_agent_model(path, review_harness, "reviewer")
            assert pick["model"] == lane["model"], (
                f"{review_harness} review-worker-cross must degrade to the standard lane model"
            )

    def test_orchestrate_category_matches_real_harness_config(self):
        # `orchestrate` is the session's own category, and it is the one category that reaches a real
        # config file. Claude Code's is jq-patched into settings.json at apply time and Codex's is
        # a hand-kept literal, so a wrong row ships silently to the session default.
        import ai_models

        path = REPO / "home/.chezmoidata/ai_models"
        category_models = ai_models.load_category_models(path)

        claude_orchestrate = category_models["claude_code"]["orchestrate"]
        codex_orchestrate = category_models["codex"]["orchestrate"]

        for profile in ("work", "personal"):
            settings = json.loads((REPO / f"home/dot_claude/settings.{profile}.json").read_text(encoding="utf-8"))
            assert settings["model"] == claude_orchestrate["model"], (
                f"claude settings.{profile}.json model {settings['model']!r} != "
                f"category_models.claude_code.orchestrate.model {claude_orchestrate['model']!r}"
            )
            assert settings["effortLevel"] == claude_orchestrate["effort"], (
                f"claude settings.{profile}.json effortLevel {settings['effortLevel']!r} != "
                f"category_models.claude_code.orchestrate.effort {claude_orchestrate['effort']!r}"
            )

            config = (REPO / f"home/dot_codex/private_config.{profile}.toml").read_text(encoding="utf-8")
            model = re.search(r'^model\s*=\s*"([^"]+)"', config, re.MULTILINE)
            effort = re.search(r'^model_reasoning_effort\s*=\s*"([^"]+)"', config, re.MULTILINE)
            assert model and model.group(1) == codex_orchestrate["model"], (
                f"codex private_config.{profile}.toml model "
                f"{(model.group(1) if model else None)!r} != "
                f"category_models.codex.orchestrate.model {codex_orchestrate['model']!r}"
            )
            assert effort and effort.group(1) == codex_orchestrate["effort"], (
                f"codex private_config.{profile}.toml model_reasoning_effort "
                f"{(effort.group(1) if effort else None)!r} != "
                f"category_models.codex.orchestrate.effort {codex_orchestrate['effort']!r}"
            )

    def test_codex_defaults_and_agent_lanes_are_gpt55_xhigh_except_mechanical(self):
        import ai_models

        registry = REPO / "home/.chezmoidata/ai_models"
        expected_model = "gpt-5.5"
        expected_effort = "xhigh"
        expected_service_tier = "default"
        category_models = ai_models.load_category_models(registry)["codex"]

        self.assertEqual(category_models["mechanical"]["model"], "gpt-5.4")
        self.assertEqual(category_models["mechanical"]["effort"], "high")
        # memory is the deliberately-cheap smol row: it reuses the verified mechanical pair.
        self.assertEqual(category_models["memory"]["model"], "gpt-5.4")
        self.assertEqual(category_models["memory"]["effort"], "high")
        for category, row in category_models.items():
            if category in ("mechanical", "memory"):
                continue
            with self.subTest(surface="category", name=category):
                self.assertEqual(row["model"], expected_model)
                self.assertEqual(row["effort"], expected_effort)

        for role in ("review-worker", "findings-auditor", "adversarial-verifier", "criteria-verifier"):
            with self.subTest(surface="review_resolver", name=role):
                self.assertEqual(ai_models.resolve_review_agent_model(registry, "codex", role)["model"], expected_model)

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
                self.assertIn('"harness" "codex"', config)
                self.assertRegex(config, re.compile(rf'^service_tier\s*=\s*"{expected_service_tier}"$', re.MULTILINE))
                if profile.name == "readonly_smol.toml.tmpl":
                    # smol is a bindings-resolved memory agent, not a review lane: it goes
                    # through agent-model.partial and carries the memory row's effort.
                    self.assertIn('includeTemplate "agent-model.partial"', config)
                    memory_effort = category_models["memory"]["effort"]
                    self.assertRegex(
                        config, re.compile(rf'^model_reasoning_effort\s*=\s*"{memory_effort}"$', re.MULTILINE)
                    )
                    continue
                self.assertIn("review-agent-model.partial", config)
                self.assertRegex(
                    config, re.compile(rf'^model_reasoning_effort\s*=\s*"{expected_effort}"$', re.MULTILINE)
                )

    def test_every_bound_agent_resolves_on_every_harness(self):
        # The three-table lookup is only useful if it is total: an agent bound to a category that
        # a harness cannot price resolves to None, and both the template partial and the hook then
        # fall through to whatever the caller asked for. Silent, and exactly the leak being closed.
        import ai_models

        path = REPO / "home/.chezmoidata/ai_models"
        categories = ai_models.load_agent_categories(path)
        bindings = ai_models.load_agent_bindings(path)
        category_models = ai_models.load_category_models(path)

        for category, spec in categories.items():
            assert spec["family"] in ("primary", "counter"), (
                f"agent_categories.{category}.family is {spec['family']!r}, expected primary or counter"
            )
            assert "band" not in spec, f"agent_categories.{category} must route directly, not through a band"
            for harness, harness_categories in category_models.items():
                assert category in harness_categories, (
                    f"agent_categories.{category} has no category_models.{harness}.{category} row"
                )

        for agent, category in bindings.items():
            assert category in categories, f"agent_bindings.{agent} names unknown category {category!r}"
            for harness in category_models:
                pick = ai_models.resolve_agent_model(path, harness, agent)
                assert pick is not None and pick["model"], f"{agent} does not resolve to a model on {harness}"

    def test_the_refute_category_changes_family_or_declares_same_family_status(self):
        # `refute` exists to break a conclusion, and a refuter from the lanes' own family is worth
        # much less. Where a harness can field a second family it must be a different one; where it
        # deliberately stays same-family for capability, resolution has to report reduced
        # independence. Other missing-counter cases are degraded.
        import ai_models

        path = REPO / "home/.chezmoidata/ai_models"
        category_models = ai_models.load_category_models(path)
        reduced_independence_harnesses = {"omp"}

        def family(model: str) -> str:
            base = model.rsplit("/", 1)[-1].lstrip("@")
            for name in ("claude", "gpt", "gemini", "grok", "composer", "kimi", "glm"):
                if name in base:
                    return name
            return base

        for harness, harness_categories in category_models.items():
            review = harness_categories["review"]
            refute = harness_categories["refute"]
            pick = ai_models.resolve_agent_model(path, harness, "adversarial-verifier")
            verifier_status = refute.get("verifier_status")
            if verifier_status == "reduced_independence":
                assert harness in reduced_independence_harnesses, (
                    f"category_models.{harness}.refute declares reduced_independence unexpectedly"
                )
                assert pick["degraded"] is False, (
                    f"category_models.{harness}.refute declares reduced_independence but resolution says degraded"
                )
                assert pick["verifier_status"] == "reduced_independence"
                continue
            if verifier_status == "degraded":
                assert pick["degraded"] is True
                assert pick["verifier_status"] == "degraded"
                continue
            assert verifier_status == "cross_family", (
                f"category_models.{harness}.refute must declare verifier_status, got {verifier_status!r}"
            )
            assert pick["degraded"] is False, f"category_models.{harness}.refute resolves degraded"
            assert pick["verifier_status"] == "cross_family"
            assert family(review["model"]) != family(refute["model"]), (
                f"category_models.{harness}.refute {refute['model']!r} shares a family with {review['model']!r}"
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

    def test_omp_category_models_use_native_role_tokens(self) -> None:
        # OMP already has role indirection, so the repo maps categories to local role tokens rather
        # than pretending cost bands exist there. Review and refute both use advisor;
        # the status reports reduced independence because both review and refute resolve through
        # the same advisor role.
        import ai_models

        path = REPO / "home/.chezmoidata/ai_models"
        category_models = ai_models.load_category_models(path)["omp"]
        roles = self._omp_model_roles()

        assert set(roles) == {"work", "personal"}, f"unexpected OMP profiles {sorted(roles)}"
        # User call 2026-08-30: work rides the Cursor backend, personal rides the Codex backend,
        # and both profiles pin smol to cursor/default — the discovered cursor catalog's "Auto"
        # router id (reasoning off, so no :level suffix). The openai-codex catalog is OpenAI-only,
        # so the personal advisor shares gpt-5.5 with the primaries.
        expected_roles = {
            "work": {
                "default": "cursor/gpt-5.5:xhigh",
                "smol": "cursor/default",
                "vision": "cursor/gpt-5.5:xhigh",
                "slow": "cursor/gpt-5.5:xhigh",
                "plan": "cursor/gpt-5.5:xhigh",
                "task": "cursor/gpt-5.5:xhigh",
                "advisor": "cursor/claude-opus-5-high:high",
            },
            "personal": {
                "default": "openai-codex/gpt-5.5:xhigh",
                "smol": "cursor/default",
                "vision": "openai-codex/gpt-5.5:xhigh",
                "slow": "openai-codex/gpt-5.5:xhigh",
                "plan": "openai-codex/gpt-5.5:xhigh",
                "task": "openai-codex/gpt-5.5:xhigh",
                "advisor": "openai-codex/gpt-5.5:xhigh",
            },
        }
        for profile, mapping in roles.items():
            assert {"default", "smol", "plan", "task", "advisor"} <= set(mapping), (
                f"omp {profile} modelRoles lacks category routing roles: {mapping!r}"
            )
            assert mapping == expected_roles[profile], f"omp {profile} modelRoles drifted: {mapping!r}"
        assert category_models["lookup"]["model"] == "@smol"
        assert category_models["mechanical"]["model"] == "@task"
        assert category_models["research"]["model"] == "@task"
        assert category_models["implement"]["model"] == "@task"
        assert category_models["orchestrate"]["model"] == "@plan"
        assert category_models["review"]["model"] == "@advisor"
        assert category_models["refute"]["model"] == "@advisor"
        assert category_models["refute"]["verifier_status"] == "reduced_independence"
        # memory deliberately bypasses the role table: modelRoles.smol (deepseek) failed the
        # live scribe probes, and pinning the direct id leaves the lookup lane on @smol untouched.
        # The `:high` suffix is load-bearing: agent frontmatter carries only the model string
        # (agent-model.partial renders `$pick.model`), and omp's spawn precedence honors an
        # explicit `:level` suffix while the `effort` YAML field is never rendered for omp.
        assert category_models["memory"]["model"] == "openrouter/google/gemini-3.7-flash:high"
        assert category_models["memory"]["effort"] == "high"

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

        category_models = ai_models.load_category_models(REPO / "home/.chezmoidata/ai_models")
        for category, row in category_models["claude_code"].items():
            check(f"category_models.claude_code.{category}", row.get("model", ""))

        for profile in ("personal", "work"):
            settings = json.loads((REPO / f"home/dot_claude/settings.{profile}.json").read_text(encoding="utf-8"))
            check(f"claude settings.{profile}.json model", settings.get("model", ""))

    def test_claude_code_mechanical_category_uses_sonnet46_high(self):
        import ai_models

        row = ai_models.load_category_models(REPO / "home/.chezmoidata/ai_models")["claude_code"]["mechanical"]

        self.assertEqual("claude-sonnet-4-6", row["model"])
        self.assertEqual("high", row["effort"])
        self.assertNotEqual("claude-sonnet-4.6", row["model"])
        self.assertNotEqual("claude-4.6-sonnet", row["model"])

    def test_gpt55_is_always_pinned_at_xhigh_effort(self):
        # Standing policy: gpt-5.5 is only ever run at xhigh effort, in every harness and category.
        # Cursor spells the same tier as `extra-high` in the model id.
        # The effort lives in a different place per harness (a yaml `effort`, a model-id suffix,
        # a `:thinking` suffix, model_reasoning_effort, effortLevel), so drift is easy and silent.
        import ai_models

        offenders: list[str] = []

        def check(where: str, model: str, effort: str | None) -> None:
            if "gpt-5.5" not in model or "gpt-5.5-codex" in model:
                return
            # Cursor bakes effort into the id; Pi/OMP use a `:level` suffix.
            suffix = re.search(r"gpt-5\.5[-:]([a-z-]+)", model)
            if suffix and suffix.group(1) not in ("xhigh", "extra-high"):
                offenders.append(f"{where}: model {model!r} is not xhigh effort")
            if effort is not None and effort != "xhigh":
                offenders.append(f"{where}: effort {effort!r} is not xhigh (model {model!r})")

        category_models = ai_models.load_category_models(REPO / "home/.chezmoidata/ai_models")
        for harness, harness_categories in category_models.items():
            for category, row in harness_categories.items():
                check(f"category_models.{harness}.{category}", row.get("model", ""), row.get("effort"))

        registry = REPO / "home/.chezmoidata/ai_models"
        for harness in ("claude", "codex", "copilot", "cursor", "gemini", "pi", "omp"):
            for role in ("reviewer", "adversarial-verifier", "criteria-verifier"):
                pick = ai_models.resolve_review_agent_model(registry, harness, role)
                if pick:
                    check(f"review model {harness}.{role}", pick["model"], None)

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

            pi = json.loads((REPO / f"home/dot_pi/agent/readonly_settings.{profile}.json").read_text(encoding="utf-8"))
            check(
                f"pi readonly_settings.{profile}.json",
                pi.get("defaultModel", ""),
                pi.get("defaultThinkingLevel"),
            )

        assert not offenders, "gpt-5.5 must always run at xhigh effort:\n  " + "\n  ".join(offenders)

    def test_category_models_are_short_context_by_default(self):
        # Standing policy: short context everywhere unless the model/harness lacks a short selector
        # or the user explicitly requested long context for that harness. Any other `long` row is
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
            if harness == "gemini":
                if context != "long":
                    offenders.append(f"{where}: Gemini categories are user-pinned to long context, got {context!r}")
                return
            if context != "short":
                offenders.append(f"{where}: context is {context!r}, expected 'short' (model {model!r})")

        category_models = ai_models.load_category_models(REPO / "home/.chezmoidata/ai_models")
        for harness, harness_categories in category_models.items():
            for category, row in harness_categories.items():
                check(f"category_models.{harness}.{category}", harness, row.get("model", ""), row.get("context"))

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
        pi_default = "openai/gpt-5.5"
        pi_mechanical = "deepseek/deepseek-v4-flash"
        pi_refute = "anthropic/claude-sonnet-4.6"
        optional = "moonshotai/kimi-k3"
        glm = "z-ai/glm-5.2"
        counter = "openai/gpt-5.6-terra"
        default_selector = f"openrouter/{default}"
        pi_default_selector = f"openrouter/{pi_default}"
        pi_mechanical_selector = f"openrouter/{pi_mechanical}"
        pi_refute_selector = f"openrouter/{pi_refute}"
        optional_selector = f"openrouter/{optional}"
        glm_selector = f"openrouter/{glm}"
        expected_default_provider_routing = {
            "preferred_min_throughput": 24,
            "quantizations": ["fp8", "fp16", "bf16", "fp32"],
        }
        expected_glm_provider_routing = {
            "preferred_min_throughput": 24,
            "quantizations": ["fp8", "fp16", "bf16", "fp32"],
        }
        expected_optional_provider_routing = {
            "only": ["fireworks", "together", "baseten"],
            "max_price": {"completion": 16},
        }
        registry = REPO / "home/.chezmoidata/ai_models"
        provider_models = [
            row["id"] for row in ai_models.load_provider_models(registry) if row["provider"] == "openrouter"
        ]
        # Shared OpenRouter wrappers keep the DeepSeek/Kimi/GLM/Terra route. Pi has its own
        # harness-native selector set because it can pass OpenRouter ids directly.
        self.assertEqual([default, optional, glm, counter], provider_models)
        self.assertEqual(
            [
                {"id": pi_default_selector, "recommended": True},
                {"id": pi_mechanical_selector},
                # memory lane (smol): gemini-3.7-flash, live-probed 2026-08-29.
                {"id": "openrouter/google/gemini-3.7-flash"},
                {"id": pi_refute_selector},
                {"id": optional_selector},
                {"id": glm_selector},
            ],
            ai_models.load_pi_extra_models(registry),
        )

        for profile in ("work", "personal"):
            settings = json.loads((REPO / f"home/dot_pi/agent/readonly_settings.{profile}.json").read_text())
            self.assertEqual("openrouter", settings["defaultProvider"])
            self.assertEqual(pi_default, settings["defaultModel"])
            self.assertEqual("xhigh", settings["defaultThinkingLevel"])

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
            for routing in (
                default_compat["openRouterRouting"],
                optional_compat["openRouterRouting"],
                glm_compat["openRouterRouting"],
            ):
                self.assertNotIn("sort", routing)
                self.assertNotIn("order", routing)
                self.assertNotIn("allow_fallbacks", routing)
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

        pi_lane = ai_models.resolve_review_agent_model(registry, "pi", "reviewer")
        pi_verifier = ai_models.resolve_review_agent_model(registry, "pi", "adversarial-verifier")
        self.assertEqual(f"{pi_default_selector}:xhigh", pi_lane["model"])
        self.assertEqual(f"{pi_refute_selector}:xhigh", pi_verifier["model"])
        category_models = ai_models.load_category_models(registry)["pi"]
        for category in ("lookup", "research", "implement", "orchestrate", "review"):
            self.assertEqual(f"{pi_default_selector}:xhigh", category_models[category]["model"], category)
            self.assertEqual("xhigh", category_models[category]["effort"], category)
        self.assertEqual(f"{pi_mechanical_selector}:xhigh", category_models["mechanical"]["model"])
        self.assertEqual("xhigh", category_models["mechanical"]["effort"])
        self.assertEqual(f"{pi_refute_selector}:xhigh", category_models["refute"]["model"])
        self.assertEqual("xhigh", category_models["refute"]["effort"])
        # memory moved off deepseek after the live scribe-dedupe failure (2026-08-29);
        # gemini-3.7-flash tops out at `high` — no xhigh exists for it.
        self.assertEqual("openrouter/google/gemini-3.7-flash:high", category_models["memory"]["model"])
        self.assertEqual("high", category_models["memory"]["effort"])

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
        # Neither profile's modelRoles route through OpenRouter anymore (work → Cursor backend,
        # personal → Codex backend, 2026-08-30); the provider order must keep listing openrouter
        # for both profiles because the memory lane and models.yml preset routes still ride it.
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
        # routing omits sort so OpenRouter's default load balancer keeps uptime, then
        # price-weights remaining endpoints, with a 300 t/s preferred floor (OpenRouter
        # deprioritizes slower endpoints; it does not hard-exclude them). Output cap is the
        # endpoint max completion (131072), not a 2048-token ceiling. Not a Cerebras-only whitelist.
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
            "local OPENROUTER_PROVIDER_ROUTING = { preferred_min_throughput = 300 }",
            neovim,
        )
        self.assertIn("provider = OPENROUTER_PROVIDER_ROUTING,", neovim)
        self.assertNotIn('sort = "price"', neovim)
        self.assertNotIn('only = { "cerebras" }', neovim)
        self.assertNotIn("quantizations", neovim)
        self.assertNotIn("fireworks", neovim)
        for variable in ("OPENROUTER_MODEL", "OPENROUTER_NITRO", "OPENROUTER_THINKING", "OPENROUTER_REASONING_EFFORT"):
            self.assertNotIn(variable, neovim)

    def test_lookup_category_stays_exact_retrieval_only(self):
        # `lookup` is exact retrieval by a smarter caller, not semantic discovery. It can use the
        # smallest local role because no conclusion-forming agent is allowed to bind to it.
        import ai_models

        expected = {
            "claude_code": (
                "claude-fable-5-1",
                "low",
            ),  # Anthropic-only; all bands fable (5: user call 2026-08-05; 5.1: 2026-09-01)
            "codex": ("gpt-5.5", "xhigh"),  # user-selected all-band Codex policy
            "copilot": ("gpt-5.5", "xhigh"),
            "cursor": ("gpt-5.6-sol-high", "high"),  # captured Cursor Task-enum primary selector
            "gemini": ("gemini-3.1-pro-preview", "high"),  # agy's Gemini 3.1 Pro selector
            "pi": ("openrouter/openai/gpt-5.5:xhigh", "xhigh"),  # OpenRouter-only lookup route
            "omp": ("@smol", "xhigh"),  # a role token; the concrete pick is asserted below
        }

        path = REPO / "home/.chezmoidata/ai_models"
        category_models = ai_models.load_category_models(path)
        assert set(category_models) == set(expected), (
            f"harness set changed: {sorted(set(category_models) ^ set(expected))}; add its lookup pick here"
        )
        for harness, (model, effort) in expected.items():
            row = category_models[harness]["lookup"]
            assert row["model"] == model, (
                f"category_models.{harness}.lookup.model is {row['model']!r}, expected {model!r}"
            )
            assert row["effort"] == effort, (
                f"category_models.{harness}.lookup.effort is {row['effort']!r}, expected {effort!r}"
            )

        # `composer-2.5-fast` is a speed tier with the same intelligence at 6x the price
        # ($3/$15 against $0.5/$2.5, cursor.com/docs/models), so no category may reach for it.
        for category, row in category_models["cursor"].items():
            assert row["model"] != "composer-2.5-fast", (
                f"category_models.cursor.{category} is composer-2.5-fast; composer-2.5 is the same model for a sixth"
            )

        # OMP resolves lookup through modelRoles; @smol is Cursor's Auto router on both profiles
        # (user call 2026-08-30).
        roles = self._omp_model_roles()
        assert roles["work"]["smol"] == "cursor/default"
        assert roles["personal"]["smol"] == "cursor/default"

        # Copilot is the one harness where the lookup category reaches a deployed file rather than a
        # rendered profile, so check the model actually landed on every lookup-bound built-in.
        #
        # Copilot may legitimately have none: `lookup` narrowed to exact retrieval only (see the
        # investigation note in tiering.yaml agent_bindings), and Copilot ships no such built-in —
        # `explore` forms conclusions, so it is `research`. An empty set means the lookup category is
        # simply unreachable on this harness, not that a pin was dropped, so the loop below is a
        # no-op rather than a failure. If a lookup-bound Copilot agent is ever added, it is checked.
        bindings = ai_models.load_agent_bindings(path)
        copilot = json.loads((REPO / "home/private_dot_copilot/settings.json").read_text(encoding="utf-8"))[
            "subagents"
        ]["agents"]
        lookup_agents = [name for name in copilot if bindings.get(name) == "lookup"]
        copilot_model, copilot_effort = expected["copilot"]
        for name in lookup_agents:
            assert copilot[name]["model"] == copilot_model, (
                f"copilot settings.json {name} model {copilot[name]['model']!r} != {copilot_model!r}"
            )
            assert copilot[name]["effortLevel"] == copilot_effort, (
                f"copilot settings.json {name} effortLevel is {copilot[name]['effortLevel']!r}, expected {copilot_effort!r}"
            )

    def test_generated_subagent_rosters_match_the_category_registry(self):
        # Copilot pins subagent models inside a settings file the harness rewrites at runtime,
        # so it cannot be a chezmoi template over the registry. The generator reconciles it.
        import subprocess

        result = subprocess.run(
            [sys.executable, str(REPO / "scripts/generate_subagent_models.py"), "check"],
            capture_output=True,
            text=True,
            cwd=str(REPO),
        )
        assert result.returncode == 0, (
            "Copilot subagent roster diverges from category_models; run "
            f"`python3 scripts/generate_subagent_models.py write`:\n{result.stderr}"
        )

    def test_the_deployed_agent_projection_is_current(self):
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

    def test_cursor_categories_stay_inside_the_captured_task_enum(self):
        # Cursor validates Task.model against a narrower enum than `cursor-agent models` before the
        # hook rewrite takes effect. The enum is the consumer contract; the broader catalog is only
        # the source for main-session model availability.
        import ai_models

        mirrors = json.loads((REPO / "home/dot_config/ai/readonly_model-mirrors.v1.json").read_text(encoding="utf-8"))
        curated = mirrors["harnesses"]["cursor"]["curated"]
        assert curated["complete"] is True, "Cursor curated catalog must stay complete for category validation"
        cursor_catalog = set(curated["models"])
        # Probed 2026-08-29 (cursor-agent 2026.08.28-a7f9513) from the Task-spawn
        # "Invalid model selection" rejection listing.
        cursor_task_models = {
            "claude-fable-5-high",
            "claude-opus-5-high",
            "claude-sonnet-5-thinking-max",
            "composer-2.5",
            "composer-2.5-fast",
            "cursor-grok-4.5-high-fast",
            "cursor-grok-4.6-xhigh-fast",
            "gemini-3.7-flash-high",
            "gpt-5.6-sol-high",
            "gpt-5.6-terra-max",
        }

        category_models = ai_models.load_category_models(REPO / "home/.chezmoidata/ai_models")["cursor"]
        for category, row in category_models.items():
            model = row.get("model")
            if not model:
                continue
            if model == "auto":
                # `auto` is Cursor's router selector, not a catalog model, so it is deliberately
                # absent from both sets above (same policy as the copilot catalog's `auto`
                # exclusion). Live-verified 2026-08-30 (cursor-agent 2026.08.28-a7f9513): a Task
                # spawn passing model "auto" through an unbound subagent_type (band gate no-op)
                # was accepted by the enum validation that runs before hook rewrites, and an
                # interactive `cursor-agent --model auto` tmux session completed a full turn.
                continue
            assert model in cursor_task_models, (
                f"category_models.cursor.{category} is {model!r}, which the captured Cursor Task enum does not "
                f"contain; refresh the Task enum proof or pick one of {sorted(cursor_task_models)}"
            )
            assert model in cursor_catalog, (
                f"category_models.cursor.{category} is {model!r}, which the verified Cursor catalog does not contain; "
                f"refresh the catalog or pick one of {sorted(cursor_catalog)}"
            )

    def test_claude_settings_keep_thinking_disabled(self):
        # category_models.claude_code declares thinking "off" for every Anthropic category. The only
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
        # Anthropic models think by default on Copilot. The registry pins Sonnet/Fable lanes as
        # non-thinking picks, which is only true while the launcher exports this env var:
        # app.js Q3e() feeds it to nativeModelClientDefaultOptionsJson, which sets thinkingBudget.
        self.assert_file_contains(
            "home/exact_lib/exact_,copilot/main.py",
            'os.environ.setdefault("COPILOT_DISABLE_ANTHROPIC_THINKING", "1")',
        )
