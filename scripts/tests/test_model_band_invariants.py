#!/usr/bin/env python3
"""Focused tests for agent instruction invariants."""

from __future__ import annotations

import json
import os
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
            "k-agent-deep-review",
            "k-agent-review-worker",
            "k-agent-review-worker-cross",
            "k-agent-findings-auditor",
            "k-agent-pr-necessity-auditor",
            "k-agent-live-ui-review",
            "k-agent-adversarial-verifier",
            "k-agent-criteria-verifier",
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
        #
        # One declared hole: `claude-fable-5.1` sits in the snapshot ahead of org enablement (user
        # call), while the last live probe — `copilot -p --model claude-fable-5.1` on CLI 1.0.82,
        # 2026-09-01 — answered "not available". So this test proves the refute / lanes_cross picks
        # are declared in the catalog, not that the CLI accepts them today; harness-catalogs.yaml
        # carries that caveat on the row itself.
        import ai_models

        registry = REPO / "home/.chezmoidata/ai_models"
        available = {row["id"] for row in ai_models.load_copilot_models(registry)}

        category_models = ai_models.load_category_models(registry)["copilot"]
        review_roles = (
            "k-agent-deep-review",
            "k-agent-review-worker",
            "k-agent-review-worker-cross",
            "k-agent-findings-auditor",
            "k-agent-pr-necessity-auditor",
            "k-agent-live-ui-review",
            "k-agent-adversarial-verifier",
            "k-agent-criteria-verifier",
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

    def test_copilot_category_matrix_uses_sol_with_requested_exceptions(self):
        import ai_models

        rows = ai_models.load_category_models(REPO / "home/.chezmoidata/ai_models")["copilot"]
        settings = json.loads((REPO / "home/private_dot_copilot/settings.json").read_text(encoding="utf-8"))

        # Three tiers (user call 2026-09-07): T1 research/orchestrate/review on the session model
        # gpt-5.6-sol/xhigh (it superseded gpt-5.5 at the same effort, user call 2026-09-07), T2
        # implement on claude-opus-5/high, T3 mechanical/memory on claude-sonnet-5/high.
        for category in ("research", "orchestrate", "review"):
            with self.subTest(category=category):
                self.assertEqual("gpt-5.6-sol", rows[category]["model"])
                self.assertEqual("xhigh", rows[category]["effort"])
        self.assertEqual("gpt-5.6-sol", settings["model"])
        self.assertEqual("xhigh", settings["effortLevel"])
        self.assertEqual("claude-opus-5", rows["implement"]["model"])
        self.assertEqual("high", rows["implement"]["effort"])
        self.assertEqual("claude-sonnet-5", rows["mechanical"]["model"])
        self.assertEqual("high", rows["mechanical"]["effort"])
        self.assertEqual("claude-fable-5.1", rows["refute"]["model"])
        self.assertEqual("high", rows["refute"]["effort"])
        self.assertEqual("cross_family", rows["refute"]["verifier_status"])
        self.assertEqual("claude-sonnet-5", rows["memory"]["model"])
        self.assertEqual("high", rows["memory"]["effort"])
        self.assertEqual("short", rows["memory"]["context"])

    def test_cursor_category_matrix_uses_task_enum_models_with_requested_exceptions(self):
        import ai_models

        rows = ai_models.load_category_models(REPO / "home/.chezmoidata/ai_models")["cursor"]

        for category in ("research", "orchestrate", "review"):
            with self.subTest(category=category):
                self.assertEqual("gpt-5.6-sol-high", rows[category]["model"])
                self.assertEqual("high", rows[category]["effort"])
                self.assertEqual("long", rows[category]["context"])
        # T2 implement (user call 2026-09-07): Opus 5 High is in the live Task enum and exists only
        # as a 1M id on Cursor, hence long context.
        self.assertEqual("claude-opus-5-high", rows["implement"]["model"])
        self.assertEqual("high", rows["implement"]["effort"])
        self.assertEqual("long", rows["implement"]["context"])
        # Cheap lanes use the `auto` router selector (user call 2026-08-30): Cursor picks the
        # small model itself. Live-verified 2026-08-30 (cursor-agent 2026.08.28-a7f9513): a Task
        # spawn with an explicit model "auto" was accepted (caller models are validated before
        # hook rewrites, so the probe hit the real enum), and interactive `cursor-agent --model
        # auto` completed a full turn.
        self.assertEqual("auto", rows["mechanical"]["model"])
        self.assertEqual("", rows["mechanical"]["effort"])
        self.assertEqual("short", rows["mechanical"]["context"])
        self.assertEqual("claude-fable-5-1-thinking-high", rows["refute"]["model"])
        self.assertEqual("high", rows["refute"]["effort"])
        self.assertEqual("long", rows["refute"]["context"])
        self.assertEqual("cross_family", rows["refute"]["verifier_status"])
        # memory (smol) rides the same `auto` router pick.
        self.assertEqual("auto", rows["memory"]["model"])
        self.assertEqual("short", rows["memory"]["context"])

    def test_gemini_category_matrix_uses_pro_with_flash_mechanical_long_context(self):
        import ai_models

        rows = ai_models.load_category_models(REPO / "home/.chezmoidata/ai_models")["gemini"]

        for category in ("research", "implement", "orchestrate", "review", "refute"):
            with self.subTest(category=category):
                self.assertEqual("gemini-3.1-pro-preview", rows[category]["model"])
                self.assertEqual("high", rows[category]["effort"])
                self.assertEqual("long", rows[category]["context"])
        self.assertEqual("gemini-3.8-flash", rows["mechanical"]["model"])
        self.assertEqual("high", rows["mechanical"]["effort"])
        self.assertEqual("long", rows["mechanical"]["context"])
        self.assertEqual("gemini-3.8-flash", rows["memory"]["model"])
        # memory records `low` (flash is slow, user call 2026-09-07). Antigravity's dynamic
        # flash-tier subagents take no effort dial, so the row is recorded intent, not a wire field.
        self.assertEqual("low", rows["memory"]["effort"])
        self.assertEqual("degraded", rows["refute"]["verifier_status"])

    def test_memory_category_binds_k_agent_smol_and_projects_into_the_deployed_bands(self):
        # k-agent-smol is the ,ai-kb operator: every harness must resolve it through the memory
        # category, and the deployed band projection must pin the same pick so the band
        # gate clamps delegated k-agent-smol calls.
        import ai_models

        registry = REPO / "home/.chezmoidata/ai_models"
        assert ai_models.load_agent_bindings(registry)["k-agent-smol"] == "memory"
        category_models = ai_models.load_category_models(registry)
        bands = json.loads((REPO / "home/dot_config/ai/readonly_agent-bands.v1.json").read_text(encoding="utf-8"))
        for harness, rows in category_models.items():
            with self.subTest(harness=harness):
                pick = ai_models.resolve_agent_model(registry, harness, "k-agent-smol")
                self.assertEqual(rows["memory"]["model"], pick["model"])
                self.assertEqual(
                    rows["memory"]["model"], bands["harnesses"][harness]["agents"]["k-agent-smol"]["model"]
                )

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

        review_agents = (
            "k-agent-reviewer",
            "k-agent-deep-review",
            "k-agent-findings-auditor",
            "k-agent-live-ui-review",
            "k-agent-adversarial-verifier",
        )
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
            pick = ai_models.resolve_review_agent_model(path, review_harness, "k-agent-review-worker-cross")
            assert pick is not None, f"review-worker-cross does not resolve on {review_harness}"
            assert pick["source"] == "override"
            assert pick["model"] == model
            assert "effort" in pick, "override picks merge the category row underneath"
        for review_harness in ("claude", "codex"):
            pick = ai_models.resolve_review_agent_model(path, review_harness, "k-agent-review-worker-cross")
            assert pick is not None, f"review-worker-cross does not resolve on {review_harness}"
            lane = ai_models.resolve_review_agent_model(path, review_harness, "k-agent-reviewer")
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
            # Claude Code's per-model `modelSettings[<id>].effortLevel` wins over the top-level
            # `effortLevel`, so the session model's own row is the effort `orchestrate` actually
            # gets. `personal` deliberately runs the session model one notch below the registry
            # row (docs/topics/ai-assistants/tool-configs/claude-gemini.md: "the personal Claude
            # profile keeps ... its `claude-fable-5-1` high-effort override ... the global effort
            # setting remains xhigh"). The exception is pinned rather than skipped, so changing
            # either side without updating the other fails instead of drifting silently.
            declared_exception = {("personal", "claude-fable-5-1"): "high"}
            for model_id, overrides in settings.get("modelSettings", {}).items():
                if "effortLevel" not in overrides:
                    continue
                expected = declared_exception.get(
                    (profile, model_id),
                    claude_orchestrate["effort"] if model_id == claude_orchestrate["model"] else None,
                )
                assert expected is not None, (
                    f"claude settings.{profile}.json modelSettings[{model_id!r}] pins an effort for a "
                    "model no category names; declare it or drop it"
                )
                assert overrides["effortLevel"] == expected, (
                    f"claude settings.{profile}.json modelSettings[{model_id!r}].effortLevel "
                    f"{overrides['effortLevel']!r} != {expected!r}"
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

    def test_codex_defaults_and_agent_lanes_keep_effort_across_retired_model_migration(self):
        import ai_models

        registry = REPO / "home/.chezmoidata/ai_models"
        # Tiers (user call 2026-09-07, revised the same day once gpt-6-astra proved absurdly
        # expensive): T1 orchestrate/research on the session default gpt-5.6-sol/high, T2 implement
        # deliberately collapsed onto T3 gpt-5.6-terra/high (Codex 0.153.2 names Terra as the retired
        # GPT-5.4 replacement), astra reserved for review and refute.
        expected = {
            "research": ("gpt-5.6-sol", "high"),
            "orchestrate": ("gpt-5.6-sol", "high"),
            "review": ("gpt-6-astra", "high"),
            "implement": ("gpt-5.6-terra", "high"),
            "refute": ("gpt-6-astra", "high"),
            "mechanical": ("gpt-5.6-terra", "high"),
            "memory": ("gpt-5.6-terra", "high"),
        }
        expected_root_model, expected_root_effort = expected["orchestrate"]
        expected_service_tier = "default"
        category_models = ai_models.load_category_models(registry)["codex"]

        self.assertEqual(set(expected), set(category_models))
        for category, (model, effort) in expected.items():
            with self.subTest(surface="category", name=category):
                self.assertEqual(category_models[category]["model"], model)
                self.assertEqual(category_models[category]["effort"], effort)

        bindings = ai_models.load_agent_bindings(registry)
        # Review lanes render the review row and the verifiers render refute (both gpt-6-astra).
        for role in (
            "k-agent-review-worker",
            "k-agent-findings-auditor",
            "k-agent-adversarial-verifier",
            "k-agent-criteria-verifier",
        ):
            with self.subTest(surface="review_resolver", name=role):
                model, _ = expected[bindings[role]]
                self.assertEqual(ai_models.resolve_review_agent_model(registry, "codex", role)["model"], model)

        for profile in ("personal", "work"):
            config = (REPO / f"home/dot_codex/private_config.{profile}.toml").read_text(encoding="utf-8")
            with self.subTest(surface="root_profile", name=profile):
                self.assertRegex(config, re.compile(rf'^model\s*=\s*"{re.escape(expected_root_model)}"$', re.MULTILINE))
                self.assertRegex(
                    config, re.compile(rf'^model_reasoning_effort\s*=\s*"{expected_root_effort}"$', re.MULTILINE)
                )
                self.assertRegex(config, re.compile(rf'^service_tier\s*=\s*"{expected_service_tier}"$', re.MULTILINE))

        agents = sorted((REPO / "home/dot_codex/exact_agents").glob("*.toml.tmpl"))
        self.assertTrue(agents, "Codex agent profile set is empty")
        for profile in agents:
            config = profile.read_text(encoding="utf-8")
            agent = profile.name.removeprefix("readonly_").removesuffix(".toml.tmpl")
            category = bindings[agent]
            with self.subTest(surface="agent_profile", name=profile.name):
                self.assertIn('"harness" "codex"', config)
                self.assertRegex(config, re.compile(rf'^service_tier\s*=\s*"{expected_service_tier}"$', re.MULTILINE))
                if category in ("memory", "mechanical"):
                    # Bindings-resolved cheap lanes, not review lanes: they go through
                    # agent-model.partial.
                    self.assertIn('includeTemplate "agent-model.partial"', config)
                else:
                    self.assertIn("review-agent-model.partial", config)
                # The model is rendered from the registry but model_reasoning_effort is a hand-kept
                # literal, so it has to carry the effort of the row it renders (the bound category).
                _, lane_effort = expected[category]
                self.assertRegex(config, re.compile(rf'^model_reasoning_effort\s*=\s*"{lane_effort}"$', re.MULTILINE))

    def test_codex_agent_registry_matches_the_profile_files_it_points_at(self):
        # Without an `[agents.<name>]` entry the files under ~/.codex/agents are never read:
        # `spawn_agent` only sees roles named in that table. So a profile with no pointer is
        # silently unreachable (the lane runs as the parent instead of failing), and a pointer to a
        # missing file errors at spawn time. Work registers the full set; personal deliberately
        # carries only the two profiles every machine needs (k-agent-smol, k-agent-mechanical), so
        # it must be a subset, never a different set.
        profiles = {
            path.name.removeprefix("readonly_").removesuffix(".toml.tmpl")
            for path in (REPO / "home/dot_codex/exact_agents").glob("*.toml.tmpl")
        }
        assert profiles, "no codex agent profiles found"

        registered = {}
        for profile in ("personal", "work"):
            config = (REPO / f"home/dot_codex/private_config.{profile}.toml").read_text(encoding="utf-8")
            names = set(re.findall(r"^\[agents\.([^\]]+)\]", config, re.MULTILINE))
            pointers = {
                match.rsplit("/", 1)[-1].removesuffix(".toml")
                for match in re.findall(r'^config_file\s*=\s*"([^"]+)"', config, re.MULTILINE)
            }
            assert names == pointers, (
                f"codex private_config.{profile}.toml registers {sorted(names)} but points at {sorted(pointers)}"
            )
            registered[profile] = pointers

        assert registered["work"] == profiles, (
            "codex private_config.work.toml must register every exact_agents profile: "
            f"unregistered {sorted(profiles - registered['work'])}, "
            f"dangling pointers {sorted(registered['work'] - profiles)}"
        )
        assert registered["personal"] <= registered["work"], (
            f"codex personal registers roles work does not: {sorted(registered['personal'] - registered['work'])}"
        )
        assert registered["personal"] <= profiles, (
            f"codex private_config.personal.toml points at missing profiles: "
            f"{sorted(registered['personal'] - profiles)}"
        )

    def test_codex_roles_use_supported_overrides_and_keep_instruction_boundaries(self):
        # Codex 0.153.2 core/src/agent/role.rs AgentRoleOverrides projects these fields.
        # approval_policy/sandbox_mode are ignored; role_tests.rs keeps parent.permissions.
        supported = {
            "developer_instructions",
            "model",
            "model_reasoning_effort",
            "model_reasoning_summary",
            "model_verbosity",
            "personality",
            "service_tier",
            "features",
            "skills",
        }
        for path in sorted((REPO / "home/dot_codex/exact_agents").glob("*.toml.tmpl")):
            with self.subTest(profile=path.name):
                source = path.read_text(encoding="utf-8")
                header, instructions = source.split('developer_instructions = """', 1)
                keys = set(re.findall(r"^(\w+)\s*=", header, re.MULTILINE)) - {"name", "description"}
                self.assertLessEqual(keys, supported)
                self.assertIn('include "dot_config/exact_tmux/agent_prompts/leaf-boundary.txt"', instructions)
                self.assertRegex(instructions, r"Read and follow ~/.agents/skills/k-[^\s]+/references/[^\s]+\.md")
                self.assertIn("Never edit", instructions)
                self.assertIn("commit", instructions)
                self.assertIn("push", instructions)

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

    def test_every_harness_separates_implement_from_orchestrate_and_mechanical(self):
        # Three tiers per harness (user call 2026-09-07; SOP §3.7 implement dispatch gate): every
        # implementation edit runs on the T2 implement lane while the orchestrator keeps
        # decomposition, judging and verification on T1. The gate only earns its dispatch cost if T2
        # is a genuinely different model from T1 (else delegating an edit costs what inlining it
        # costs) and from T3 (else the implement lane is just the mechanical lane).
        import ai_models

        category_models = ai_models.load_category_models(REPO / "home/.chezmoidata/ai_models")
        omp_roles = self._omp_model_roles()

        def resolved(harness: str, category: str) -> str:
            model = category_models[harness][category]["model"]
            if harness == "omp":
                assert model.startswith("@"), f"category_models.omp.{category} is not a role token: {model!r}"
                return omp_roles[model[1:]]
            return model

        for harness in category_models:
            with self.subTest(harness=harness):
                implement = resolved(harness, "implement")
                orchestrate = resolved(harness, "orchestrate")
                mechanical = resolved(harness, "mechanical")
                if harness == "codex":
                    # User call 2026-09-07: gpt-6-astra proved absurdly expensive, sol became the T1
                    # workhorse, and the implementer was deliberately collapsed onto the T3 terra pick
                    # (cheapest implementer) rather than sharing T1.
                    assert implement == mechanical, (
                        f"category_models.codex.implement {implement!r} != mechanical {mechanical!r}"
                    )
                    assert implement != orchestrate, (
                        f"category_models.codex.implement {implement!r} is the orchestrate (T1) pick"
                    )
                    continue
                assert implement != mechanical, (
                    f"category_models.{harness}.implement {implement!r} is the mechanical (T3) pick"
                )
                if harness == "gemini":
                    # Antigravity's invoke_subagent tier surface is pro/flash only, so no T2 tier
                    # exists: implement shares the pro tier with orchestrate.
                    assert implement == orchestrate, (
                        f"category_models.gemini.implement {implement!r} != orchestrate {orchestrate!r}"
                    )
                    continue
                assert implement != orchestrate, (
                    f"category_models.{harness}.implement {implement!r} is the orchestrate (T1) pick"
                )

    def test_the_refute_category_changes_family_or_declares_same_family_status(self):
        # `refute` exists to break a conclusion, and a refuter from the lanes' own family is worth
        # much less. Where a harness can field a second family it must be a different one; where it
        # deliberately stays same-family for capability, resolution has to report reduced
        # independence. Other missing-counter cases are degraded.
        import ai_models

        path = REPO / "home/.chezmoidata/ai_models"
        category_models = ai_models.load_category_models(path)
        omp_roles = self._omp_model_roles()

        def resolved(harness: str, model: str) -> str:
            # OMP spells its rows as `@role` tokens, so comparing the tokens themselves ('default'
            # vs 'advisor') is a tautology: any two distinct roles look cross-family even when both
            # resolve to the same vendor. Resolve through modelRoles before asking about families.
            if harness != "omp":
                return model
            assert model.startswith("@"), f"category_models.omp names a raw model: {model!r}"
            return omp_roles[model.removeprefix("@")]

        def family(model: str) -> str:
            base = model.rsplit("/", 1)[-1]
            for name in ("claude", "gpt", "gemini", "grok", "composer", "kimi", "glm"):
                if name in base:
                    return name
            return base

        for harness, harness_categories in category_models.items():
            review = harness_categories["review"]
            refute = harness_categories["refute"]
            pick = ai_models.resolve_agent_model(path, harness, "k-agent-adversarial-verifier")
            verifier_status = refute.get("verifier_status")
            if verifier_status == "reduced_independence":
                assert pick["degraded"] is False, (
                    f"category_models.{harness}.refute declares reduced_independence but resolution says degraded"
                )
                assert pick["verifier_status"] == "reduced_independence"
                assert family(resolved(harness, review["model"])) == family(resolved(harness, refute["model"])), (
                    f"category_models.{harness}.refute declares reduced_independence but is cross-family"
                )
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
            review_family = family(resolved(harness, review["model"]))
            refute_family = family(resolved(harness, refute["model"]))
            assert review_family != refute_family, (
                f"category_models.{harness}.refute {refute['model']!r} shares the {refute_family!r} family "
                f"with review {review['model']!r}"
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

    def test_the_band_gate_rewrites_cursor_subagent_launches_but_keeps_registry_lane_picks(self) -> None:
        # Cursor transcript exports label the delegation tool `Subagent` (2026-09-04) while the
        # bundle still says `taskToolCall`; the hook payload name is unverified, so a matcher or
        # DELEGATION_TOOLS that knows only one of them can let every Cursor lane run on whatever
        # model the caller typed. The gate must also leave ANY registry lane pick alone on a
        # generic subagent type — since schema 1.4.0 the pass-through set is `lane_models` (every
        # bound agent's resolved pick), not just the counter and cheap lanes — or a cross-family
        # verifier launched as `generalPurpose` is rewritten back onto the finder family.
        import subprocess

        hooks = json.loads((REPO / "home/dot_cursor/hooks.json").read_text(encoding="utf-8"))
        matchers = [e["matcher"] for e in hooks["hooks"]["preToolUse"] if "band_gate.py" in e.get("command", "")]
        assert matchers and all(re.fullmatch(matchers[0], name) for name in ("Subagent", "Task")), matchers

        projection = REPO / "home/dot_config/ai/readonly_agent-bands.v1.json"
        cursor = json.loads(projection.read_text(encoding="utf-8"))["harnesses"]["cursor"]
        implement_model = cursor["agents"]["generalPurpose"]["model"]
        refute_model = cursor["agents"]["k-agent-adversarial-verifier"]["model"]
        assert refute_model in cursor["counter_models"]
        assert refute_model != implement_model

        def gate(tool_name: str, model: str) -> dict:
            payload = {
                "tool_name": tool_name,
                "tool_input": {"subagent_type": "generalPurpose", "model": model, "prompt": "x"},
            }
            result = subprocess.run(
                [sys.executable, str(REPO / "home/exact_dot_agents/exact_hooks/executable_band_gate.py")],
                input=json.dumps(payload),
                capture_output=True,
                text=True,
                env={**os.environ, "AGENT_BAND_HARNESS": "cursor", "AGENT_BANDS_FILE": str(projection)},
                check=True,
            )
            return json.loads(result.stdout)

        # An in-enum model that is not the band pick and that no registry lane asked for.
        escape = "claude-sonnet-5-thinking-max"
        assert escape != implement_model and escape not in cursor["lane_models"]
        bypass = gate("Subagent", escape)
        assert bypass["updated_input"]["model"] == implement_model, bypass
        assert bypass["updated_input"]["prompt"] == "x", "Cursor updated_input must echo untouched keys"
        assert gate("Task", escape)["updated_input"]["model"] == implement_model
        assert gate("Subagent", refute_model) == {}, "registry refute pick must pass through untouched"
        # Cursor never scans ~/.cursor/agents, so the mechanical lane is dispatched as the generic
        # type carrying the registry mechanical pick; that pick must pass like any other lane pick.
        mechanical_model = cursor["agents"]["k-agent-mechanical"]["model"]
        assert set(cursor["cheap_lane_models"]) == {mechanical_model, cursor["agents"]["k-agent-smol"]["model"]}
        assert mechanical_model != implement_model
        assert gate("Subagent", mechanical_model) == {}, "registry mechanical pick must pass through untouched"
        # Only the generic `implement` type may carry another lane's pick; a bound cheap-band or
        # research-band profile asking for it is still an escape and gets its own band back.
        smol_model = cursor["agents"]["k-agent-smol"]["model"]
        assert cursor["agents"]["k-agent-smol"]["category"] == "memory"
        smol = subprocess.run(
            [sys.executable, str(REPO / "home/exact_dot_agents/exact_hooks/executable_band_gate.py")],
            input=json.dumps(
                {"tool_name": "Subagent", "tool_input": {"subagent_type": "k-agent-smol", "model": refute_model}}
            ),
            capture_output=True,
            text=True,
            env={**os.environ, "AGENT_BAND_HARNESS": "cursor", "AGENT_BANDS_FILE": str(projection)},
            check=True,
        )
        assert json.loads(smol.stdout)["updated_input"]["model"] == smol_model, smol.stdout
        assert gate("Shell", escape) == {}, "non-delegation tools stay no-ops"

        # A BYOK route pins every band to one wire model; the counter pass-through must not
        # let a registry id escape that route.
        byok = subprocess.run(
            [sys.executable, str(REPO / "home/exact_dot_agents/exact_hooks/executable_band_gate.py")],
            input=json.dumps(
                {"tool_name": "Subagent", "tool_input": {"subagent_type": "generalPurpose", "model": refute_model}}
            ),
            capture_output=True,
            text=True,
            env={
                **os.environ,
                "AGENT_BAND_HARNESS": "cursor",
                "AGENT_BANDS_FILE": str(projection),
                "AGENT_BAND_MODEL_OVERRIDE": "byok/one-model",
            },
            check=True,
        )
        assert json.loads(byok.stdout)["updated_input"]["model"] == "byok/one-model"

        # Claude's Agent tool takes family aliases only; a full registry id must still reach the
        # alias clamp instead of passing through as a "counter model".
        claude = json.loads(projection.read_text(encoding="utf-8"))["harnesses"]["claude_code"]
        full_id = claude["counter_models"][0]
        alias = claude["agents"]["general-purpose"]["alias"]
        clamp = subprocess.run(
            [sys.executable, str(REPO / "home/exact_dot_agents/exact_hooks/executable_band_gate.py")],
            input=json.dumps(
                {"tool_name": "Agent", "tool_input": {"subagent_type": "general-purpose", "model": full_id}}
            ),
            capture_output=True,
            text=True,
            env={**os.environ, "AGENT_BAND_HARNESS": "claude_code", "AGENT_BANDS_FILE": str(projection)},
            check=True,
        )
        assert json.loads(clamp.stdout)["hookSpecificOutput"]["updatedInput"]["model"] == alias, clamp.stdout

        # The alias rank is the tier ladder, not model size: under the 2026-09-07 tiers `fable`
        # (T1) is the research / review thinker, `opus` (T2) implements and `sonnet` (T3) is the
        # cheap lane. So asking for `fable` from a T2 or T3 band is an upward escape, while a T1
        # agent asking for `opus` is a legal downgrade. A rank table that still files `fable` next
        # to `haiku` inverts both, which is what these deployed-hook probes catch. The aliases are
        # asserted first so the probes fail loudly if the alias projection drifts instead of
        # silently testing a different ladder rung.
        agents = claude["agents"]
        assert agents["cli_help"]["alias"] == "sonnet", agents["cli_help"]
        assert agents["general-purpose"]["alias"] == "opus", agents["general-purpose"]
        assert agents["k-agent-code-searcher"]["alias"] == "fable", agents["k-agent-code-searcher"]
        assert agents["k-agent-smol"]["alias"] == "sonnet", agents["k-agent-smol"]

        def claude_alias(agent: str, model: str) -> str | None:
            """The alias the deployed hook leaves in place; None when it emitted the `{}` no-op."""
            result = subprocess.run(
                [sys.executable, str(REPO / "home/exact_dot_agents/exact_hooks/executable_band_gate.py")],
                input=json.dumps({"tool_name": "Agent", "tool_input": {"subagent_type": agent, "model": model}}),
                capture_output=True,
                text=True,
                env={**os.environ, "AGENT_BAND_HARNESS": "claude_code", "AGENT_BANDS_FILE": str(projection)},
                check=True,
            )
            out = json.loads(result.stdout)
            if out == {}:
                return None
            return out["hookSpecificOutput"]["updatedInput"]["model"]

        # Upward: the T3 mechanical and T2 implement bands may not reach the T1 thinker.
        assert claude_alias("cli_help", "fable") == "sonnet", "a mechanical lane must not reach T1 Fable"
        assert claude_alias("general-purpose", "fable") == "opus", "an implement lane must not reach T1 Fable"
        # Sideways / downward: a T1 research lane dropping to the T2 implementer is allowed.
        assert claude_alias("k-agent-code-searcher", "opus") is None, "a T1 lane may ask for a cheaper alias"
        # Upward again: the memory lane sits on T3 and must not climb to T2.
        assert claude_alias("k-agent-smol", "opus") == "sonnet", "a memory lane must not reach T2 Opus"
        # Cheaper than its own band is never an escape.
        assert claude_alias("general-purpose", "sonnet") is None, "an implement lane may ask for T3 Sonnet"

    def test_the_band_gate_passes_any_explicit_lane_pick_on_a_generic_subagent_type(self) -> None:
        # Most harnesses cannot reach the per-lane profiles at all (Cursor never scans
        # ~/.cursor/agents), so a research or review launch arrives as the generic `implement`
        # type carrying the lane's registry pick as an explicit `model`. A pass-through list
        # covering only the counter and cheap lanes silently collapses those launches onto the
        # implement band -- a T1 research spawn ends up on the T2 implement model. The rule is
        # category-aware: on an `implement`-bound generic type any registry lane pick survives,
        # a non-registry model is rewritten, and a bound non-generic agent asking for another
        # lane's pick is still clamped to its own band.
        import subprocess

        projection_path = REPO / "home/dot_config/ai/readonly_agent-bands.v1.json"
        projection = json.loads(projection_path.read_text(encoding="utf-8"))
        assert projection["schema_version"] == "1.4.0", (
            "lane_models is a schema addition; bump generate_agent_bands.py SCHEMA_VERSION"
        )

        def gate_model(payload: dict, harness: str) -> str | None:
            """The model the gate leaves in place: None when it emitted a no-op."""
            result = subprocess.run(
                [sys.executable, str(REPO / "home/exact_dot_agents/exact_hooks/executable_band_gate.py")],
                input=json.dumps(payload),
                capture_output=True,
                text=True,
                env={**os.environ, "AGENT_BAND_HARNESS": harness, "AGENT_BANDS_FILE": str(projection_path)},
                check=True,
            )
            out = json.loads(result.stdout)
            if not out:
                return None
            for updated in (
                out.get("updated_input"),
                out.get("modifiedArgs"),
                out.get("hookSpecificOutput", {}).get("updatedInput"),
            ):
                if isinstance(updated, dict) and "model" in updated:
                    return updated["model"]
            raise AssertionError(f"unrecognised gate output shape: {result.stdout}")

        cursor = projection["harnesses"]["cursor"]
        implement_model = cursor["agents"]["generalPurpose"]["model"]
        research_model = cursor["agents"]["cursor-guide"]["model"]
        assert cursor["agents"]["cursor-guide"]["category"] == "research"
        assert research_model != implement_model, "probe needs the research and implement bands to differ"
        assert {research_model, implement_model} <= set(cursor["lane_models"])

        def cursor_launch(agent: str, model: str) -> str | None:
            return gate_model(
                {"tool_name": "Subagent", "tool_input": {"subagent_type": agent, "model": model, "prompt": "x"}},
                "cursor",
            )

        # 1. The generic type carrying the research lane's pick: the launch a research spawn makes.
        assert cursor_launch("generalPurpose", research_model) is None, (
            "a research lane dispatched as generalPurpose must keep its registry pick"
        )
        # 2. The generic type carrying its own band pick: pass-through or an unchanged rewrite.
        own = cursor_launch("generalPurpose", implement_model)
        assert own in (None, implement_model), own
        # 3. A model no lane asked for is still rewritten to the generic type's band.
        escape = "claude-sonnet-5-thinking-max"
        assert escape not in cursor["lane_models"]
        assert cursor_launch("generalPurpose", escape) == implement_model
        # 4. A bound agent reaching for another lane's pick is clamped to its own band.
        assert cursor_launch("cursor-guide", implement_model) == research_model

        # 5. Codex exposes the generic implement type as `worker` through spawn_agent.
        codex = projection["harnesses"]["codex"]
        codex_implement = codex["agents"]["worker"]["model"]
        codex_research = codex["agents"]["cursor-guide"]["model"]
        assert codex["agents"]["worker"]["category"] == "implement"
        assert {codex_research, codex_implement} <= set(codex["lane_models"]), codex["lane_models"]
        assert codex_research != codex_implement
        codex_model = gate_model(
            {"tool_name": "spawn_agent", "tool_input": {"agent_type": "worker", "model": codex_research}},
            "codex",
        )
        assert codex_model in (None, codex_research), (
            f"codex worker carrying the research pick was rewritten to {codex_model}"
        )

        # 6. Copilot's generic type is `task`, and its extension hands tool_input over as a JSON
        # string rather than an object.
        copilot = projection["harnesses"]["copilot"]
        copilot_implement = copilot["agents"]["task"]["model"]
        copilot_research = copilot["agents"]["cursor-guide"]["model"]
        assert copilot_research != copilot_implement
        copilot_model = gate_model(
            {"tool_name": "task", "tool_input": json.dumps({"agent": "task", "model": copilot_research})},
            "copilot",
        )
        assert copilot_model in (None, copilot_research), (
            f"copilot task carrying the research pick was rewritten to {copilot_model}"
        )

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
        # than pretending cost bands exist there. Review rides the session model (@default, Anthropic)
        # and refute rides @advisor (openai-codex), so the status is cross_family: the counter comes
        # from a genuinely different vendor. It reported reduced_independence only while review also
        # rode @advisor.
        import ai_models

        path = REPO / "home/.chezmoidata/ai_models"
        category_models = ai_models.load_category_models(path)["omp"]
        roles = self._omp_model_roles()

        # User call 2026-09-07: one profile-independent modelRoles block, three tiers. T1
        # default/plan/slow/vision ride the native anthropic provider on Fable 5.1 :high; T2 task is
        # Opus 5 :high (the native `task` agent and every implement worker land there); T3 smol is
        # Sonnet 5 :high (cursor/default ran the @smol lanes over the cursor-agent transport and
        # died on Cursor's free-request limit); tiny/commit ride Sonnet 5 :medium; advisor is the
        # native openai-codex provider on gpt-6-astra:high. Every built-in role is pinned so
        # nothing falls through to the harness default.
        expected_roles = {
            "default": "anthropic/claude-fable-5.1:high",
            "smol": "anthropic/claude-sonnet-5:high",
            "slow": "anthropic/claude-fable-5.1:high",
            "vision": "anthropic/claude-fable-5.1:high",
            "plan": "anthropic/claude-fable-5.1:high",
            "commit": "anthropic/claude-sonnet-5:medium",
            "tiny": "anthropic/claude-sonnet-5:medium",
            "task": "anthropic/claude-opus-5:high",
            "advisor": "openai-codex/gpt-6-astra:high",
        }
        assert roles == expected_roles, f"omp modelRoles drifted: {roles!r}"
        # T2 is a different model from T1 and T3 from T2; otherwise a delegated implement or
        # mechanical edit costs exactly what inlining it costs.
        assert roles["task"] != roles["default"]
        assert roles["smol"] != roles["task"]
        assert roles["smol"] != roles["default"]
        assert category_models["research"]["model"] == "@default"
        assert category_models["implement"]["model"] == "@task"
        assert category_models["orchestrate"]["model"] == "@plan"
        assert category_models["review"]["model"] == "@default"
        assert category_models["refute"]["model"] == "@advisor"
        assert category_models["refute"]["verifier_status"] == "cross_family"
        # mechanical and memory both ride @smol. mechanical used to name @task, which resolved to
        # the session's own Fable model, so a delegated mechanical edit cost the same as inlining
        # it; memory used to pin a direct gemini id while modelRoles.smol was deepseek (failed the
        # live scribe probes) and rides the role token again now that smol is Sonnet 5 (user call
        # 2026-09-07).
        assert category_models["mechanical"]["model"] == "@smol"
        assert category_models["memory"]["model"] == "@smol"

    @staticmethod
    def _omp_model_roles() -> dict[str, str]:
        """Parse the single profile-independent `modelRoles` block out of OMP's config template."""
        source = (REPO / "home/dot_omp/private_agent/readonly_config.yml.tmpl").read_text(encoding="utf-8")
        lines = source.splitlines()
        headers = [index for index, line in enumerate(lines) if line.startswith("modelRoles:")]
        assert len(headers) == 1, f"OMP config template must declare modelRoles exactly once, found {len(headers)}"
        first_branch = next((index for index, line in enumerate(lines) if ".isWork" in line), len(lines))
        assert headers[0] < first_branch, "OMP modelRoles must precede every isWork branch (profile-independent)"
        roles: dict[str, str] = {}
        for line in lines[headers[0] + 1 :]:
            if line.strip() and not line.startswith("  "):
                break
            match = re.match(r"^  ([\w-]+):\s*(\S+)\s*$", line)
            if match:
                roles[match.group(1)] = match.group(2)
        assert roles, "no modelRoles block found in OMP's config template"
        return roles

    def test_claude_code_models_are_claude_family_selectors(self):
        # Claude Code does not remap unknown model ids: they reach the API and come back as
        # "API model not found". A cross-vendor id here (e.g. a shared gpt-5.5 orchestration
        # default) silently breaks every native session once the merge script patches settings.json.
        import ai_models

        # The alias set the Agent tool and settings.json accept. `fable` is one of them: the band
        # gate's `_CLAUDE_RANK` and generate_agent_bands.py's CLAUDE_ALIASES both carry it, so
        # omitting it here would reject a legal `fable` selector as "cannot run".
        aliases = {"default", "opus", "opusplan", "sonnet", "haiku", "fable"}

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

    def test_claude_code_mechanical_category_uses_sonnet5_high(self):
        import ai_models

        row = ai_models.load_category_models(REPO / "home/.chezmoidata/ai_models")["claude_code"]["mechanical"]

        self.assertEqual("claude-sonnet-5", row["model"])
        self.assertEqual("high", row["effort"])
        # Claude Code hyphenates point versions and 404s on the dotted form; a future point release
        # of this row must keep the hyphenated spelling.
        self.assertNotEqual("claude-sonnet-4.6", row["model"])
        self.assertNotEqual("claude-4.6-sonnet", row["model"])
        self.assertNotRegex(row["model"], r"claude-\w+-\d+\.\d+")

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
        # One OpenRouter id carries the `recommended` picker entry, T2 implement (:high) and
        # refute (:xhigh) since gpt-5.6-sol superseded gpt-5.5 (user call 2026-09-07); Sonnet 4.6
        # stays listed as selectable-only, like kimi-k3 and glm-5.2.
        pi_route = "openai/gpt-5.6-sol"
        pi_mechanical = "deepseek/deepseek-v4-flash"
        pi_memory = "google/gemini-3.8-flash"
        pi_selectable_sonnet = "anthropic/claude-sonnet-4.6"
        optional = "moonshotai/kimi-k3"
        glm = "z-ai/glm-5.2"
        counter = "openai/gpt-5.6-terra"
        default_selector = f"openrouter/{default}"
        pi_route_selector = f"openrouter/{pi_route}"
        pi_mechanical_selector = f"openrouter/{pi_mechanical}"
        pi_memory_selector = f"openrouter/{pi_memory}"
        optional_selector = f"openrouter/{optional}"
        glm_selector = f"openrouter/{glm}"
        pi_selectable_sonnet_selector = f"openrouter/{pi_selectable_sonnet}"
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
                # Native Anthropic session model: the T1 rows ride it, so the Pi curated picker
                # lists it first (mirror test_SHOULD_keep_pi_review_policy_pins_in_pi_catalogs).
                {"id": "anthropic/claude-fable-5.1"},
                # The curated OpenRouter picker, not the category-pick list: `recommended` marks the
                # route to reach for by hand, and gpt-5.6-sol keeps it because it carries both T2
                # implement (:high) and `refute` (:xhigh). It appears once, not once per effort.
                {"id": pi_route_selector, "recommended": True},
                {"id": pi_mechanical_selector},
                # memory lane (smol): gemini-3.8-flash, superseding the 3.7-flash the lane was
                # live-probed on 2026-08-29.
                {"id": pi_memory_selector},
                # Selectable-only since the retier swapped review onto Anthropic and refute onto
                # the OpenAI route; no pi category names it now, like kimi-k3 and glm-5.2 below.
                {"id": pi_selectable_sonnet_selector},
                {"id": optional_selector},
                {"id": glm_selector},
            ],
            ai_models.load_pi_extra_models(registry),
        )

        for profile in ("work", "personal"):
            settings = json.loads((REPO / f"home/dot_pi/agent/readonly_settings.{profile}.json").read_text())
            # User call 2026-09-07: Pi's interactive default routes through the native anthropic
            # provider on Fable 5.1 at high effort, not OpenRouter — and since the same retier
            # moved T1 research/orchestrate/review onto that selector, the session default and the
            # T1 band are now the same model. The `openai/gpt-5.6-sol` OpenRouter selector above
            # (pi_route/pi_route_selector) backs the harness-native "recommended" extra-models
            # entry plus the `implement` and `refute` bands, not this default.
            self.assertEqual("anthropic", settings["defaultProvider"])
            self.assertEqual("claude-fable-5.1", settings["defaultModel"])
            self.assertEqual("high", settings["defaultThinkingLevel"])

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

        # User call 2026-09-07 (Pi retier): T1 research/orchestrate/review left OpenRouter for the
        # native anthropic provider on Fable 5.1 at `high` — the same selector the interactive
        # default uses above — so the review lane resolves there too. T2 implement stays
        # gpt-5.6-sol:high, T3 mechanical deepseek-v4-flash:xhigh and memory gemini-3.8-flash:low.
        # refute rides gpt-5.6-sol:xhigh — the same id as implement at a higher effort, and still the
        # cross-family counter to an Anthropic review lane (it was Sonnet 4.6 while review rode
        # GPT-5.5; both sides swapped, then GPT-5.5 gave way to GPT-5.6 SOL on 2026-09-07).
        pi_t1 = "anthropic/claude-fable-5.1:high"
        pi_lane = ai_models.resolve_review_agent_model(registry, "pi", "k-agent-reviewer")
        pi_verifier = ai_models.resolve_review_agent_model(registry, "pi", "k-agent-adversarial-verifier")
        self.assertEqual(pi_t1, pi_lane["model"])
        self.assertEqual(f"{pi_route_selector}:xhigh", pi_verifier["model"])
        category_models = ai_models.load_category_models(registry)["pi"]
        for category in ("research", "orchestrate", "review"):
            self.assertEqual(pi_t1, category_models[category]["model"], category)
            self.assertEqual("high", category_models[category]["effort"], category)
        self.assertEqual(f"{pi_route_selector}:high", category_models["implement"]["model"])
        self.assertEqual("high", category_models["implement"]["effort"])
        self.assertEqual(f"{pi_mechanical_selector}:xhigh", category_models["mechanical"]["model"])
        self.assertEqual("xhigh", category_models["mechanical"]["effort"])
        self.assertEqual(f"{pi_route_selector}:xhigh", category_models["refute"]["model"])
        self.assertEqual("xhigh", category_models["refute"]["effort"])
        self.assertEqual("cross_family", category_models["refute"]["verifier_status"])
        # memory moved off deepseek after the live scribe-dedupe failure (2026-08-29) and onto
        # gemini-3.8-flash on 2026-09-07; the flash line tops out at `high` — no xhigh exists for it —
        # but the lane deliberately runs `low` because flash is slow (user call 2026-09-07).
        self.assertEqual(f"{pi_memory_selector}:low", category_models["memory"]["model"])
        self.assertEqual("low", category_models["memory"]["effort"])

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

    def test_exact_retrieval_is_mechanical_not_a_separate_category(self):
        # User call 2026-09-07: the former `lookup` category folded into `mechanical`. Exact
        # caller-scoped retrieval (read --help, list named files, raw pointers) is cheap-lane work
        # with no judgment; anything that chooses or concludes is `research` on the strong model.
        # A resurrected `lookup` row would price a category no agent can be bound to again.
        import ai_models

        path = REPO / "home/.chezmoidata/ai_models"
        categories = ai_models.load_agent_categories(path)
        bindings = ai_models.load_agent_bindings(path)
        category_models = ai_models.load_category_models(path)

        assert "lookup" not in categories
        for harness, rows in category_models.items():
            assert "lookup" not in rows, f"category_models.{harness} still prices a lookup row"
        assert "lookup" not in set(bindings.values())
        # The retrieval-only built-ins ride the mechanical lane; the conclusion-forming ones do not.
        for agent in ("cli_help", "scout"):
            assert bindings[agent] == "mechanical", f"{agent} must bind to mechanical, got {bindings[agent]!r}"
        for agent in ("Explore", "explore", "explorer", "codebase_investigator", "k-agent-code-searcher"):
            assert bindings[agent] == "research", f"{agent} must stay research, got {bindings[agent]!r}"

        # `composer-2.5-fast` is a speed tier with the same intelligence at 6x the price
        # ($3/$15 against $0.5/$2.5, cursor.com/docs/models), so no category may reach for it.
        for category, row in category_models["cursor"].items():
            assert row["model"] != "composer-2.5-fast", (
                f"category_models.cursor.{category} is composer-2.5-fast; composer-2.5 is the same model for a sixth"
            )

        # OMP resolves the cheap lane through the profile-independent modelRoles block; @smol is
        # anthropic/claude-sonnet-5:high (user call 2026-09-07: cursor/default died on Cursor's
        # free-request limit).
        assert category_models["omp"]["mechanical"]["model"] == "@smol"
        assert self._omp_model_roles()["smol"] == "anthropic/claude-sonnet-5:high"

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
            # Listed by Task validation on cursor-agent 2026.09.02-c22c1a3 (2026-09-04).
            "claude-fable-5-1-thinking-high",
            "claude-fable-5-high",
            "claude-opus-5-high",
            "claude-sonnet-5-thinking-max",
            "composer-2.5",
            "composer-2.5-fast",
            "cursor-grok-4.5-high-fast",
            "cursor-grok-4.6-xhigh-fast",
            "gemini-3.7-flash-high",
            "gemini-3.8-flash-high",
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
