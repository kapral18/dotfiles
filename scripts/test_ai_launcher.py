#!/usr/bin/env python3
"""Tests for the unified `,ai` launcher."""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CORE = REPO / "home" / "exact_lib" / "exact_,ai" / "main.py"
LAUNCHER = REPO / "home" / "exact_bin" / "executable_,ai"
MODEL_MIRROR = REPO / "home" / "dot_config" / "ai" / "readonly_model-mirrors.v1.json"
MODEL_MIRROR_CONSUMER = REPO / "scripts" / "model_mirror_consumer.py"
LEAVES = {
    "cursor": ",cursor",
    "claude": "claude",
    "codex": ",codex",
    "gemini": "gemini",
    "opencode": "opencode",
    "pi": "pi",
    "copilot": ",copilot",
}


def load_core():
    spec = importlib.util.spec_from_file_location("ai_launcher", CORE)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {CORE}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class TestAiLauncher(unittest.TestCase):
    """WHEN resolving and executing unified AI harness invocations."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._home = tempfile.TemporaryDirectory()
        cls.home = Path(cls._home.name)
        deployed_mirror = cls.home / ".config" / "ai" / "model-mirrors.v1.json"
        deployed_mirror.parent.mkdir(parents=True)
        shutil.copy2(MODEL_MIRROR, deployed_mirror)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._home.cleanup()

    def run_ai(
        self,
        *args: str,
        env: dict[str, str] | None = None,
        check: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            [sys.executable, str(CORE), *args],
            cwd=REPO,
            env={**os.environ, "HOME": str(self.home), **(env or {})},
            text=True,
            capture_output=True,
            check=False,
        )
        if check and result.returncode != 0:
            self.fail(f",ai {' '.join(args)} failed\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}")
        return result

    def dry_plan(self, harness: str, *args: str) -> dict[str, object]:
        result = self.run_ai(harness, *args, "--dry-run", check=True)
        return json.loads(result.stdout)

    def test_when_each_harness_is_dry_run_it_emits_a_plan_without_executing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bindir = Path(tmp)
            marker = bindir / "executed"
            for leaf in LEAVES.values():
                fake = bindir / leaf
                fake.write_text(f"#!/bin/sh\ntouch '{marker}'\n", encoding="utf-8")
                fake.chmod(0o755)
            env = {"PATH": os.pathsep.join([str(bindir), os.environ["PATH"]])}

            for harness, leaf in LEAVES.items():
                with self.subTest(harness=harness):
                    result = self.run_ai(harness, "--dry-run", env=env, check=True)
                    plan = json.loads(result.stdout)
                    self.assertEqual("InvocationPlan", plan["kind"])
                    self.assertEqual(harness, plan["harness"]["value"])
                    self.assertEqual(leaf, plan["leaf"]["argv"][0])
                    self.assertEqual(
                        {
                            "AI_AGENT_CONNECTIVITY": "online",
                            "AI_AGENT_DEPTH": "balanced",
                            "AI_AGENT_EXECUTION": "supervised",
                        },
                        plan["leaf"]["env"],
                    )
            self.assertFalse(marker.exists())

    def test_when_aliases_expand_they_preserve_axis_semantics(self) -> None:
        plan = self.dry_plan("pi", "--alias", "audit")
        unsupported_offline = self.run_ai("pi", "--alias", "offline", "--dry-run")

        self.assertEqual("deep", plan["fields"]["depth"]["value"])
        self.assertEqual("readonly", plan["fields"]["execution"]["value"])
        self.assertEqual("online", plan["fields"]["connectivity"]["value"])
        self.assertEqual("alias", plan["fields"]["depth"]["provenance"]["kind"])
        self.assertEqual("alias:audit", plan["fields"]["execution"]["provenance"]["source"])
        self.assertIn("read,grep,find,ls", plan["leaf"]["argv"])
        self.assertEqual(2, unsupported_offline.returncode)
        self.assertIn("pi does not support explicit connectivity=offline", unsupported_offline.stderr)

    def test_when_an_explicit_value_matches_an_alias_it_wins_provenance(self) -> None:
        plan = self.dry_plan(
            "copilot",
            "--alias",
            "audit",
            "--depth",
            "deep",
            "--execution",
            "readonly",
        )

        depth = plan["fields"]["depth"]
        execution = plan["fields"]["execution"]
        self.assertEqual({"kind": "option", "source": "--depth"}, depth["provenance"]["selected"])
        self.assertEqual({"kind": "option", "source": "--execution"}, execution["provenance"]["selected"])
        self.assertIn({"kind": "alias", "source": "alias:audit", "value": "deep"}, depth["provenance"]["inputs"])
        self.assertIn(
            {"kind": "alias", "source": "alias:audit", "value": "readonly"},
            execution["provenance"]["inputs"],
        )

    def test_when_alias_and_explicit_axis_conflict_resolution_fails_visibly(self) -> None:
        result = self.run_ai("copilot", "--alias", "audit", "--execution", "autonomous", "--dry-run")

        self.assertEqual(2, result.returncode)
        self.assertIn("contradictory execution selections", result.stderr)
        self.assertNotIn("InvocationPlan", result.stdout)

    def test_when_repeated_axis_values_conflict_resolution_fails_visibly(self) -> None:
        result = self.run_ai("claude", "--depth", "fast", "--depth", "deep", "--dry-run")

        self.assertEqual(2, result.returncode)
        self.assertIn("contradictory depth selections", result.stderr)

    def test_when_leaf_args_bypass_an_owned_field_resolution_fails_visibly(self) -> None:
        result = self.run_ai(
            "copilot",
            "--alias",
            "audit",
            "--dry-run",
            "--",
            "--mode",
            "autopilot",
            "--allow-all",
        )

        self.assertEqual(2, result.returncode)
        self.assertIn("leaf argument --mode contradicts launcher-owned execution", result.stderr)

        result = self.run_ai(
            "copilot",
            "--execution",
            "supervised",
            "--dry-run",
            "--",
            "--allow-all-paths",
        )

        self.assertEqual(2, result.returncode)
        self.assertIn("leaf argument --allow-all-paths contradicts launcher-owned execution", result.stderr)

    def test_when_multi_character_or_attached_leaf_options_bypass_axes_resolution_fails(self) -> None:
        cases = [
            (
                "pi",
                ["--execution", "autonomous", "--dry-run", "--", "-xt", "bash,edit,write"],
                "leaf argument -xt contradicts launcher-owned execution",
            ),
            (
                "codex",
                ["--depth", "fast", "--dry-run", "--", '-cmodel_reasoning_effort="high"'],
                "leaf Codex config contradicts launcher-owned depth/execution",
            ),
        ]

        for harness, args, expected in cases:
            with self.subTest(harness=harness):
                result = self.run_ai(harness, *args)
                self.assertEqual(2, result.returncode)
                self.assertIn(expected, result.stderr)

    def test_when_supported_execution_is_explicit_each_harness_gets_exact_transport(self) -> None:
        cases = {
            "cursor": ("readonly", ["--mode", "plan"]),
            "claude": ("supervised", ["--permission-mode", "manual"]),
            "codex": (
                "autonomous",
                ["--sandbox", "danger-full-access", "--ask-for-approval", "never"],
            ),
            "gemini": ("readonly", ["--approval-mode", "plan"]),
            "opencode": ("autonomous", ["--auto"]),
            "pi": ("readonly", ["--tools", "read,grep,find,ls"]),
            "copilot": ("autonomous", ["--mode", "autopilot", "--allow-all"]),
        }

        for harness, (execution, expected) in cases.items():
            with self.subTest(harness=harness):
                plan = self.dry_plan(harness, "--execution", execution)
                argv = plan["leaf"]["argv"]
                cursor = 0
                for token in expected:
                    cursor = argv.index(token, cursor) + 1
                self.assertTrue(plan["fields"]["execution"]["hard"])
                self.assertEqual("applied", plan["fields"]["execution"]["transport"]["status"])

    def test_when_hard_constraint_is_unsupported_resolution_fails_instead_of_weakening(self) -> None:
        cases = [
            ("opencode", ["--execution", "readonly"], "execution=readonly"),
            ("pi", ["--execution", "supervised"], "execution=supervised"),
            ("claude", ["--connectivity", "offline"], "connectivity=offline"),
            ("cursor", ["--connectivity", "offline"], "connectivity=offline"),
            ("codex", ["--connectivity", "offline"], "connectivity=offline"),
            ("gemini", ["--connectivity", "offline"], "connectivity=offline"),
            ("opencode", ["--connectivity", "offline"], "connectivity=offline"),
            ("pi", ["--connectivity", "offline"], "connectivity=offline"),
            ("copilot", ["--connectivity", "offline"], "connectivity=offline"),
        ]

        for harness, args, label in cases:
            with self.subTest(harness=harness, label=label):
                result = self.run_ai(harness, *args, "--dry-run")
                self.assertEqual(2, result.returncode)
                self.assertIn(f"{harness} does not support explicit {label}", result.stderr)

    def test_when_pi_connectivity_is_inherited_or_online_it_handles_ambient_offline_mode(self) -> None:
        inherited = self.dry_plan("pi")
        explicit_online = self.dry_plan("pi", "--connectivity", "online")

        self.assertNotIn("PI_OFFLINE", inherited["leaf"]["unset_env"])
        self.assertIn("PI_OFFLINE", explicit_online["leaf"]["unset_env"])

    def test_when_depth_is_explicit_supported_harnesses_apply_and_others_stay_soft(self) -> None:
        cases = {
            "cursor": (["--model", "gpt-5.5"], "applied", "gpt-5.5[effort=low]"),
            "claude": ([], "applied", "--effort"),
            "codex": ([], "applied", 'model_reasoning_effort="low"'),
            "gemini": ([], "advisory", None),
            "opencode": ([], "advisory", None),
            "pi": ([], "applied", "--thinking"),
            "copilot": ([], "applied", "--effort"),
        }

        for harness, (extra, status, marker) in cases.items():
            with self.subTest(harness=harness):
                plan = self.dry_plan(harness, "--depth", "fast", *extra)
                self.assertFalse(plan["fields"]["depth"]["hard"])
                self.assertEqual(status, plan["fields"]["depth"]["transport"]["status"])
                if marker is not None:
                    self.assertIn(marker, plan["leaf"]["argv"])

    def test_when_cursor_depth_has_no_explicit_model_it_remains_soft_and_visible(self) -> None:
        plan = self.dry_plan("cursor", "--depth", "deep")

        self.assertEqual("advisory", plan["fields"]["depth"]["transport"]["status"])
        self.assertIn("explicit model", plan["fields"]["depth"]["transport"]["note"])
        self.assertNotIn("--model", plan["leaf"]["argv"])

    def test_when_provider_is_explicit_only_verified_harness_support_is_used(self) -> None:
        pi = self.dry_plan("pi", "--provider", "openrouter", "--model", "openai/gpt-5.5")
        missing_model = self.run_ai("pi", "--provider", "openrouter", "--dry-run")
        empty_model = self.run_ai("pi", "--provider", "openrouter", "--model", "", "--dry-run")
        unsupported = self.run_ai("claude", "--provider", "openrouter", "--dry-run")

        self.assertEqual(
            [",ai-selection", "--provider", "openrouter", "--model", "openai/gpt-5.5"],
            pi["selection"]["transport_trace"],
        )
        self.assertIn("--provider", pi["leaf"]["argv"])
        self.assertEqual(2, missing_model.returncode)
        self.assertIn("pi explicit provider requires a concrete model", missing_model.stderr)
        self.assertEqual(2, empty_model.returncode)
        self.assertIn("pi explicit provider requires a concrete model", empty_model.stderr)
        self.assertEqual(2, unsupported.returncode)
        self.assertIn("claude does not accept an explicit provider", unsupported.stderr)

    def test_when_availability_adapter_supplies_pi_model_provider_provenance_is_preserved(self) -> None:
        core = load_core()

        class FakeAvailability:
            def resolve(self, harness, requested_model, requested_provider):
                self.request = (harness, requested_model, requested_provider)
                return core.AvailabilitySelection(
                    model="openai/gpt-5.5",
                    provider=requested_provider,
                    model_provenance=core.Provenance("adapter", "deterministic-model"),
                    provider_provenance=core.Provenance("option", "--provider"),
                    model_is_explicit=False,
                    provider_is_explicit=True,
                )

        adapter = FakeAvailability()
        command = core.parse_cli(["pi", "--provider", "openrouter", "--dry-run"])
        plan = core.resolve_plan(command, adapter)

        self.assertEqual(("pi", None, "openrouter"), adapter.request)
        self.assertEqual(
            ("--provider", "openrouter", "--model", "openai/gpt-5.5"),
            plan.selection.transport_args,
        )
        self.assertEqual("deterministic-model", plan.selection.model_provenance.source)
        self.assertFalse(plan.selection.model_is_explicit)

    def test_when_availability_adapter_supplies_a_model_the_core_uses_the_seam(self) -> None:
        core = load_core()

        class FakeAvailability:
            def resolve(self, harness, requested_model, requested_provider):
                self.request = (harness, requested_model, requested_provider)
                return core.AvailabilitySelection(
                    model="gpt-5.5",
                    provider=None,
                    model_provenance=core.Provenance("adapter", "fake-availability"),
                    provider_provenance=core.Provenance("harness-default", "current harness config"),
                    model_is_explicit=False,
                    provider_is_explicit=False,
                )

        adapter = FakeAvailability()
        command = core.parse_cli(["cursor", "--depth", "deep", "--dry-run"])
        plan = core.resolve_plan(command, adapter)

        self.assertEqual(("cursor", None, None), adapter.request)
        self.assertIn("gpt-5.5[effort=high]", plan.actual_argv)
        self.assertEqual("fake-availability", plan.selection.model_provenance.source)

    def test_when_generated_launcher_view_is_used_the_plan_exposes_bounded_catalog_provenance(self) -> None:
        plan = self.dry_plan("gemini")

        availability = plan["selection"]["availability"]
        self.assertEqual("launcher", availability["consumer"])
        self.assertEqual("gemini", availability["harness"])
        self.assertEqual("available", availability["set"])
        self.assertEqual("known", availability["status"])
        self.assertTrue(availability["complete"])
        self.assertGreater(availability["model_count"], 0)
        self.assertEqual("~/.config/ai/model-mirrors.v1.json", availability["source"])
        self.assertNotIn("models", availability)

    def test_when_available_catalog_is_complete_an_unknown_explicit_model_fails_closed(self) -> None:
        result = self.run_ai("gemini", "--model", "not-a-real-gemini-model", "--dry-run")

        self.assertEqual(2, result.returncode)
        self.assertIn("absent from the complete generated available catalog", result.stderr)

    def test_when_available_catalog_is_incomplete_explicit_low_level_model_control_is_preserved(self) -> None:
        plan = self.dry_plan("claude", "--model", "future-claude-model")

        self.assertIn("future-claude-model", plan["leaf"]["argv"])
        self.assertFalse(plan["selection"]["availability"]["complete"])

    def test_when_generated_mirror_is_missing_resolution_fails_visibly(self) -> None:
        with tempfile.TemporaryDirectory() as home:
            result = self.run_ai("gemini", "--dry-run", env={"HOME": home})

        self.assertEqual(2, result.returncode)
        self.assertIn("generated model mirror", result.stderr)
        self.assertNotIn("InvocationPlan", result.stdout)

    def test_when_secret_bearing_leaf_options_are_planned_values_are_redacted(self) -> None:
        result = self.run_ai(
            "cursor",
            "--dry-run",
            "--",
            "--api-key",
            "top-secret-key",
            "--header=Authorization: Bearer top-secret-token",
            "review src",
            check=True,
        )

        self.assertNotIn("top-secret-key", result.stdout)
        self.assertNotIn("Authorization: ******", result.stdout)
        plan = json.loads(result.stdout)
        self.assertIn("<redacted>", plan["leaf"]["argv"])
        self.assertIn("--header=<redacted>", plan["leaf"]["argv"])
        self.assertIn("review src", plan["leaf"]["argv"])

    def test_when_sensitive_option_shapes_vary_their_values_remain_redacted(self) -> None:
        cases = {
            "claude": (
                [
                    "--settings",
                    '{"apiKey":"claude-settings-secret"}',
                    "--mcp-config",
                    '{"token":"claude-mcp-secret-one"}',
                    '{"token":"claude-mcp-secret-two"}',
                    "--verbose",
                ],
                ["claude-settings-secret", "claude-mcp-secret-one", "claude-mcp-secret-two"],
            ),
            "opencode": (["-popencode-secret"], ["opencode-secret"]),
            "pi": (["--api-key=pi-secret"], ["pi-secret"]),
            "copilot": (
                ["--additional-mcp-config", '{"Authorization":"copilot-secret"}'],
                ["copilot-secret"],
            ),
        }

        for harness, (leaf_args, secrets) in cases.items():
            with self.subTest(harness=harness):
                result = self.run_ai(
                    harness,
                    "--dry-run",
                    "--",
                    *leaf_args,
                    "review src",
                    check=True,
                )
                for secret in secrets:
                    self.assertNotIn(secret, result.stdout)
                plan = json.loads(result.stdout)
                self.assertTrue(any("<redacted>" in arg for arg in plan["leaf"]["argv"]))
                self.assertIn("review src", plan["leaf"]["argv"])
                if harness == "claude":
                    self.assertIn("--verbose", plan["leaf"]["argv"])

        assignment = self.run_ai(
            "gemini",
            "--dry-run",
            "--",
            "OPENAI_API_KEY=assignment-secret",
            check=True,
        )
        self.assertNotIn("assignment-secret", assignment.stdout)

    def test_when_explain_is_requested_it_shows_provenance_and_does_not_execute(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bindir = Path(tmp)
            marker = bindir / "executed"
            fake = bindir / "claude"
            fake.write_text(f"#!/bin/sh\ntouch '{marker}'\n", encoding="utf-8")
            fake.chmod(0o755)
            env = {"PATH": os.pathsep.join([str(bindir), os.environ["PATH"]])}

            result = self.run_ai("claude", "--alias", "audit", "--explain", env=env, check=True)

            self.assertIn("InvocationPlan", result.stdout)
            self.assertIn("depth=deep", result.stdout)
            self.assertIn("alias:audit", result.stdout)
            self.assertIn("argv:", result.stdout)
            self.assertFalse(marker.exists())

    def test_when_executing_a_real_plan_the_fake_leaf_receives_exact_argv_and_env(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bindir = root / "bin"
            bindir.mkdir()
            log = root / "leaf.json"
            fake = bindir / "claude"
            fake.write_text(
                "#!/usr/bin/env python3\n"
                "import json, os, sys\n"
                "from pathlib import Path\n"
                "Path(os.environ['AI_FAKE_LOG']).write_text(json.dumps({"
                "'argv': sys.argv[1:],"
                "'env': {key: os.environ[key] for key in "
                "['AI_AGENT_DEPTH','AI_AGENT_EXECUTION','AI_AGENT_CONNECTIVITY']}"
                "}))\n",
                encoding="utf-8",
            )
            fake.chmod(0o755)
            env = {
                "AI_FAKE_LOG": str(log),
                "PATH": os.pathsep.join([str(bindir), os.environ["PATH"]]),
            }

            result = self.run_ai(
                "claude",
                "--depth",
                "fast",
                "--execution",
                "readonly",
                "--connectivity",
                "online",
                "--",
                "--name",
                "transport-test",
                env=env,
                check=True,
            )
            payload = json.loads(log.read_text(encoding="utf-8"))

            self.assertEqual(
                [
                    "--effort",
                    "low",
                    "--permission-mode",
                    "plan",
                    "--name",
                    "transport-test",
                ],
                payload["argv"],
            )
            self.assertEqual(
                {
                    "AI_AGENT_CONNECTIVITY": "online",
                    "AI_AGENT_DEPTH": "fast",
                    "AI_AGENT_EXECUTION": "readonly",
                },
                payload["env"],
            )
            self.assertEqual("", result.stdout)

    def test_when_public_launcher_runs_it_only_delegates_to_the_deployed_core(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            deployed = home / "lib" / ",ai"
            deployed.mkdir(parents=True)
            shutil.copy2(CORE, deployed / "main.py")
            shutil.copy2(MODEL_MIRROR_CONSUMER, deployed / "model_mirror_consumer.py")
            deployed_mirror = home / ".config" / "ai" / "model-mirrors.v1.json"
            deployed_mirror.parent.mkdir(parents=True)
            shutil.copy2(MODEL_MIRROR, deployed_mirror)
            env = {**os.environ, "HOME": str(home)}
            env.pop("PYTHONPATH", None)
            result = subprocess.run(
                ["/bin/bash", str(LAUNCHER), "claude", "--dry-run"],
                cwd=REPO,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("InvocationPlan", json.loads(result.stdout)["kind"])
        self.assertLessEqual(len(LAUNCHER.read_text(encoding="utf-8").splitlines()), 15)


class CapabilityDriftTests(unittest.TestCase):
    """WHEN the hand-authored CAPABILITIES table and the observed
    model_capabilities.v1.json snapshot drift, the suite fails loudly."""

    CAPABILITIES_SNAPSHOT = REPO / "scripts" / "model_capabilities.v1.json"

    def test_verified_versions_match_the_capability_snapshot(self) -> None:
        core = load_core()
        snapshot = json.loads(self.CAPABILITIES_SNAPSHOT.read_text(encoding="utf-8"))["harnesses"]
        self.assertEqual(sorted(core.CAPABILITIES), sorted(snapshot))
        for name, capability in core.CAPABILITIES.items():
            observed = str(snapshot[name].get("identity", {}).get("version", ""))
            self.assertIn(
                capability.verified_version,
                observed,
                f"{name}: CAPABILITIES.verified_version {capability.verified_version!r} is not part of "
                f"the observed identity version {observed!r}; re-verify the harness and update both "
                f"home/exact_lib/exact_,ai/main.py and scripts/model_capabilities.v1.json together",
            )


if __name__ == "__main__":
    unittest.main()
