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
        review_roles = (
            "deep-review",
            "review-worker",
            "findings-auditor",
            "pr-necessity-auditor",
            "live-ui-review",
            "adversarial-verifier",
            "criteria-verifier",
        )

        used: set[str] = set()
        for band, row in bands.items():
            model = row.get("model")
            if model:
                used.add(model)
            counter = row.get("counter")
            if isinstance(counter, dict) and counter.get("model"):
                used.add(counter["model"])

        for role in review_roles:
            pick = ai_models.resolve_review_agent_model(registry, "copilot", role)
            if pick and pick["model"] and pick["model"] != "inherit":
                used.add(pick["model"])

        missing = sorted(model for model in used if model not in available)
        assert not missing, f"copilot policy names models not in copilot_models: {missing}"

    def test_review_model_resolver_uses_bands_except_declared_overrides(self):
        # Review routing has one source rule: override only for harness selectors that model_bands
        # cannot express, otherwise derive lane/verifier picks from the max band and its counter.
        import ai_models

        path = REPO / "home/.chezmoidata/ai_models"
        bands = ai_models.load_model_bands(path)
        overrides = ai_models.load_review_model_overrides(path)
        expected_overrides = {"claude", "gemini"}
        assert set(overrides) == expected_overrides, (
            f"review_model_overrides should stay sparse; unexpected keys {sorted(set(overrides) ^ expected_overrides)}"
        )

        review_agents = ("reviewer", "deep-review", "findings-auditor", "live-ui-review", "adversarial-verifier")
        review_harnesses = {
            "claude_code": "claude",
            **{harness: harness for harness in bands if harness != "claude_code"},
        }
        for band_harness, review_harness in review_harnesses.items():
            for agent in review_agents:
                pick = ai_models.resolve_review_agent_model(path, review_harness, agent)
                assert pick is not None, f"{agent} does not resolve on {review_harness}"
                if review_harness in overrides:
                    assert pick["source"] == "override"
                    assert pick["model"] == overrides[review_harness][pick["slot"]]
                    continue

                top = bands[band_harness]["max"]
                expected = (top.get("counter") or top)["model"] if pick["slot"] == "verifier" else top["model"]
                assert pick["source"] == "model_bands"
                assert pick["model"] == expected, (
                    f"{review_harness} {agent} resolved {pick['model']!r}, expected {expected!r} from model_bands"
                )
                if pick["slot"] == "verifier" and top.get("verifier_status") == "reduced_independence":
                    assert pick["verifier_status"] == "reduced_independence"
                    assert pick["degraded"] is False

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
                self.assertIn("review-agent-model.partial", config)
                self.assertIn('"harness" "codex"', config)
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

    def test_the_counter_band_changes_family_or_declares_same_family_status(self):
        # `refute` exists to break a conclusion, and a refuter from the lanes' own family is worth
        # much less. Where a harness can field a second family it must be a different one; where it
        # deliberately stays same-family for capability, resolution has to report reduced
        # independence. Other missing-counter cases are degraded.
        import ai_models

        path = REPO / "home/.chezmoidata/ai_models"
        bands = ai_models.load_model_bands(path)
        reduced_independence_harnesses = {"cursor", "omp"}

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
            verifier_status = top.get("verifier_status")
            if counter is None:
                if verifier_status == "reduced_independence":
                    assert harness in reduced_independence_harnesses, (
                        f"model_bands.{harness}.max declares reduced_independence unexpectedly"
                    )
                    assert pick["degraded"] is False, (
                        f"model_bands.{harness}.max declares reduced_independence but resolution says degraded"
                    )
                    assert pick["verifier_status"] == "reduced_independence"
                else:
                    assert pick["degraded"] is True, (
                        f"model_bands.{harness} has no counter, so refutation must resolve degraded"
                    )
                    assert pick["verifier_status"] == "degraded"
                continue
            assert verifier_status in (None, "cross_family"), (
                f"model_bands.{harness}.max has a counter and should not declare {verifier_status!r}"
            )
            assert pick["degraded"] is False, f"model_bands.{harness} has a counter but resolution says degraded"
            assert pick["verifier_status"] == "cross_family"
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
        self.assertEqual(f"{default_selector}:max", pi_lane["model"])
        self.assertEqual(f"{counter_selector}:max", pi_verifier["model"])
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
            "gemini": ("gemini-3.7-flash", "high"),  # Google-only catalog
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
        # smol through the OpenRouter deepseek deepseek-lanes-max preset (FP8-or-higher, 24 t/s
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
            "Copilot subagent roster diverges from model_bands; run "
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
