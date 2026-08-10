#!/usr/bin/env python3
"""Offline contract tests for the SOP policy IR/compiler/capability snapshot.

Everything here runs against synthetic /tmp fixtures. The only real-repo test,
test_committed_policy_artifacts_are_verified_read_only, verifies committed
policy artifacts without repairing stale generated files.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

import _test_support  # noqa: F401  (puts scripts/ on sys.path)
import ai_harness_capabilities as capabilities
import ai_policy_ir as ir
import compile_ai_policy as compiler
import eval_ai_policy as evals
from _test_support import REPO

FIXTURE_SOP = """# Standard Operating Procedures

---

## 0. Binding Contract

Body zero.

## 1. Purpose

Body one.
"""


def _write_fixture_repo(root: Path, sop_text: str = FIXTURE_SOP) -> None:
    (root / "home").mkdir(parents=True, exist_ok=True)
    (root / "home/readonly_AGENTS.md").write_text(sop_text, encoding="utf-8")
    (root / "home/dot_config/ai/exact_policy-ir").mkdir(parents=True, exist_ok=True)
    (root / "home/dot_config/ai/exact_policy-ir/readonly_harness-capabilities.v1.json").write_text(
        json.dumps(
            {
                "version": 1,
                "harnesses": [
                    {
                        "harness": "claude",
                        "version_evidence": "fixture",
                        "instruction_entrypoints": ["x"],
                        "hook_support": "advisory",
                        "model_mutable": True,
                        "subagent_model_binding": "static",
                        "evidence_freshness": "2026-01-01",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (root / "home/exact_dot_agents/exact_skills").mkdir(parents=True, exist_ok=True)


def _passed_ablation(root: Path, rule_id: str, consumer: str, target_disposition: str = "skill") -> dict:
    rules = {rule.id: rule for rule in ir.split_legacy_sop((root / compiler.LEGACY_PATH).read_text(encoding="utf-8"))}
    rule = rules[rule_id]
    return {
        "status": "passed",
        "target_disposition": target_disposition,
        "consumer": consumer,
        "rule_sha256": rule.sha256,
        "eval_ref": f"{rule_id}.ablation-passed",
        "consumer_sha256": hashlib.sha256((root / consumer).read_bytes()).hexdigest(),
    }


class PolicyIRTest(unittest.TestCase):
    """WHEN splitting a legacy SOP into opaque Stage 1 rules."""

    def test_round_trip_is_byte_for_byte(self):
        rules = ir.split_legacy_sop(FIXTURE_SOP)
        assert ir.render(rules) == FIXTURE_SOP

    def test_rule_ids_are_unique_and_stable(self):
        rules = ir.split_legacy_sop(FIXTURE_SOP)
        ids = [rule.id for rule in rules]
        assert ids == ["sop.0.binding-contract", "sop.1.purpose"]
        assert len(ids) == len(set(ids))

    def test_rule_ids_transliterate_accents(self):
        rules = ir.split_legacy_sop("# T\n\n---\n\n## 9. Café Policy\n\nbody\n")
        assert [rule.id for rule in rules] == ["sop.9.cafe-policy"]

    def test_high_risk_rule_ids_get_non_standard_risk_tiers(self):
        rules = ir.split_legacy_sop(
            "# T\n\n---\n\n"
            "## 0. Binding Contract\n\nbody\n\n"
            "### 2.0 Compatibility Gate\n\nbody\n\n"
            "### 3.1 Git Commit and Push Safety\n\nbody\n\n"
            "### 3.2 Ownership Gate\n\nbody\n\n"
            "### 3.6 Human-Visible Publication\n\nbody\n"
        )
        tiers = {rule.id: rule.risk_tier for rule in rules}
        assert tiers["sop.0.binding-contract"] == "safety"
        assert tiers["sop.2.0.compatibility-gate"] == "compatibility"
        assert tiers["sop.3.1.git-commit-and-push-safety"] == "git-gate"
        assert tiers["sop.3.2.ownership-gate"] == "ownership"
        assert tiers["sop.3.6.human-visible-publication"] == "publication"

    def test_rule_rejects_unknown_disposition(self):
        with self.assertRaises(ValueError):
            ir.Rule(id="x", text="t", disposition="bogus", consumer="c", risk_tier="standard", eval_ref="e")

    def test_rule_rejects_missing_eval_ref(self):
        with self.assertRaises(ValueError):
            ir.Rule(id="x", text="t", disposition="core", consumer="c", risk_tier="standard", eval_ref="")

    def test_no_headings_raises(self):
        with self.assertRaises(ValueError):
            ir.split_legacy_sop("no headings here")


class CapabilitySnapshotTest(unittest.TestCase):
    """WHEN a rule claims a harness capability the snapshot must prove or reject."""

    def _snapshot(self, **overrides):
        base = {
            "harness": "codex",
            "version_evidence": "fixture",
            "instruction_entrypoints": ("x",),
            "hook_support": "none",
            "model_mutable": True,
            "subagent_model_binding": "runtime",
            "evidence_freshness": "2026-01-01",
        }
        base.update(overrides)
        return {base["harness"]: capabilities.HarnessCapability(**base)}

    def test_wildcard_scope_never_checked(self):
        rule = ir.Rule(id="x", text="t", disposition="core", consumer="c", risk_tier="standard", eval_ref="e")
        capabilities.check_rule_capability(rule, {})  # must not raise

    def test_unknown_harness_rejected(self):
        rule = ir.Rule(
            id="x",
            text="t",
            disposition="core",
            consumer="c",
            risk_tier="standard",
            eval_ref="e",
            harness_scope="ghost",
        )
        with self.assertRaises(capabilities.UnsupportedCapabilityError):
            capabilities.check_rule_capability(rule, {})

    def test_hook_disposition_rejects_wildcard_scope(self):
        rule = ir.Rule(id="x", text="t", disposition="hook", consumer="c", risk_tier="standard", eval_ref="e")
        with self.assertRaises(capabilities.UnsupportedCapabilityError):
            capabilities.check_rule_capability(rule, self._snapshot(hook_support="blocking"))

    def test_hook_disposition_requires_blocking_support(self):
        rule = ir.Rule(
            id="x",
            text="t",
            disposition="hook",
            consumer="c",
            risk_tier="standard",
            eval_ref="e",
            harness_scope="codex",
        )
        snapshot = self._snapshot(hook_support="advisory")
        with self.assertRaises(capabilities.UnsupportedCapabilityError):
            capabilities.check_rule_capability(rule, snapshot)

    def test_hook_disposition_passes_with_blocking_support(self):
        rule = ir.Rule(
            id="x",
            text="t",
            disposition="hook",
            consumer="c",
            risk_tier="standard",
            eval_ref="e",
            harness_scope="codex",
        )
        snapshot = self._snapshot(hook_support="blocking")
        capabilities.check_rule_capability(rule, snapshot)  # must not raise

    def test_pinned_model_overlay_rejects_wildcard_harness_scope(self):
        rule = ir.Rule(
            id="x",
            text="t",
            disposition="pinned-model-overlay",
            consumer="c",
            risk_tier="standard",
            eval_ref="e",
            model_scope="claude-sonnet-5",
        )
        with self.assertRaises(capabilities.UnsupportedCapabilityError):
            capabilities.check_rule_capability(rule, self._snapshot(model_mutable=True))

    def test_pinned_model_overlay_rejects_wildcard_model_scope(self):
        rule = ir.Rule(
            id="x",
            text="t",
            disposition="pinned-model-overlay",
            consumer="c",
            risk_tier="standard",
            eval_ref="e",
            harness_scope="codex",
            model_scope="*",
        )
        snapshot = self._snapshot(model_mutable=False)
        with self.assertRaises(capabilities.UnsupportedCapabilityError):
            capabilities.check_rule_capability(rule, snapshot)

    def test_pinned_model_overlay_passes_with_explicit_model_scope(self):
        rule = ir.Rule(
            id="x",
            text="t",
            disposition="pinned-model-overlay",
            consumer="c",
            risk_tier="standard",
            eval_ref="e",
            harness_scope="codex",
            model_scope="claude-sonnet-5",
        )
        snapshot = self._snapshot(model_mutable=True)
        capabilities.check_rule_capability(rule, snapshot)  # must not raise


class CompilerTest(unittest.TestCase):
    """WHEN compiling the IR into readonly_AGENTS.md and its provenance manifest."""

    def test_generate_is_deterministic(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_fixture_repo(root)
            assert compiler.main(["generate", "--repo-root", str(root)]) == 0
            manifest_path = root / compiler.MANIFEST_PATH
            first = manifest_path.read_bytes()
            assert compiler.main(["generate", "--repo-root", str(root)]) == 0
            second = manifest_path.read_bytes()
            assert first == second

    def test_generate_is_byte_preserving(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_fixture_repo(root)
            legacy_path = root / compiler.LEGACY_PATH
            before = legacy_path.read_text(encoding="utf-8")
            assert compiler.main(["generate", "--repo-root", str(root)]) == 0
            after = legacy_path.read_text(encoding="utf-8")
            assert before == after

    def test_generate_skips_write_when_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_fixture_repo(root)
            assert compiler.main(["generate", "--repo-root", str(root)]) == 0
            legacy_path = root / compiler.LEGACY_PATH
            mtime_before = legacy_path.stat().st_mtime_ns
            assert compiler.main(["generate", "--repo-root", str(root)]) == 0
            assert legacy_path.stat().st_mtime_ns == mtime_before

    def test_generate_preserves_removed_rule_hash_ledger_when_appending_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_fixture_repo(root, sop_text="# T\n\n---\n\n## 0. Old\n\nbody\n")
            assert compiler.main(["generate", "--repo-root", str(root)]) == 0
            inventory_path = root / ir.RULE_INVENTORY_PATH
            inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
            inventory["removed_rule_sha256"] = ["keep-me"]
            inventory_path.write_text(json.dumps(inventory), encoding="utf-8")
            (root / compiler.LEGACY_PATH).write_text(
                "# T\n\n---\n\n## 0. Old\n\nbody\n\n## 1. New Rule\n\nbody\n",
                encoding="utf-8",
            )
            assert compiler.main(["generate", "--repo-root", str(root)]) == 0
            updated = json.loads(inventory_path.read_text(encoding="utf-8"))
            assert updated["removed_rule_sha256"] == ["keep-me"]
            assert "sop.1.new-rule" in updated["rule_ids"]

    def test_verify_passes_after_generate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_fixture_repo(root)
            assert compiler.main(["generate", "--repo-root", str(root)]) == 0
            assert compiler.main(["verify", "--all-targets", "--repo-root", str(root)]) == 0

    def test_verify_catches_injected_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_fixture_repo(root)
            assert compiler.main(["generate", "--repo-root", str(root)]) == 0
            legacy_path = root / compiler.LEGACY_PATH
            legacy_path.write_text(FIXTURE_SOP + "\ntampered\n", encoding="utf-8")
            assert compiler.main(["verify", "--all-targets", "--repo-root", str(root)]) == 1

    def test_generate_rejects_unknown_missing_disposition_override(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_fixture_repo(root)
            (root / ir.DISPOSITIONS_PATH).write_text(
                json.dumps(
                    {
                        "version": 1,
                        "overrides": {
                            "sop.999.injected": {
                                "disposition": "core",
                                "consumer": "home/readonly_AGENTS.md",
                                "risk_tier": "standard",
                                "eval_ref": "sop.999.injected.stage1-opaque",
                                "text": "## 999. Injected\n\nbody\n",
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )
            assert compiler.main(["generate", "--repo-root", str(root)]) == 1

    def test_generate_rejects_unsupported_harness_scope(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_fixture_repo(root, sop_text="# T\n\n---\n\n## 0. Only\n\nbody\n")
            # Monkeypatch split to inject a rule with an unsupported harness_scope.
            original_split = ir.split_legacy_sop

            def _bad_split(text: str):
                rules = original_split(text)
                bad = rules[0]
                return [
                    ir.Rule(
                        id=bad.id,
                        text=bad.text,
                        disposition="core",
                        consumer=bad.consumer,
                        risk_tier="standard",
                        eval_ref=bad.eval_ref,
                        harness_scope="ghost-harness",
                    )
                ]

            ir.split_legacy_sop = _bad_split  # type: ignore[assignment]
            try:
                assert compiler.main(["generate", "--repo-root", str(root)]) == 1
            finally:
                ir.split_legacy_sop = original_split  # type: ignore[assignment]

    def test_generate_reports_missing_capability_snapshot_cleanly(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_fixture_repo(root)
            (root / capabilities.SNAPSHOT_PATH).unlink()
            import contextlib
            import io

            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                code = compiler.main(["generate", "--repo-root", str(root)])
            assert code == 1
            assert "error:" in err.getvalue()

    def test_verify_budgets_flags_oversized_harness_overlay(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_fixture_repo(root)
            assert compiler.main(["generate", "--repo-root", str(root)]) == 0
            overlay_path = root / "home/overlay.md"
            overlay_path.write_text("x" * 3000, encoding="utf-8")
            manifest_path = root / compiler.MANIFEST_PATH
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["rules"][0]["disposition"] = "harness-overlay"
            manifest["rules"][0]["consumer"] = "home/overlay.md"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            assert (
                compiler.main(
                    [
                        "verify-budgets",
                        "--core-max-bytes",
                        "999999",
                        "--overlay-max-bytes",
                        "2048",
                        "--skill-max-bytes",
                        "8192",
                        "--description-total-max-bytes",
                        "4096",
                        "--repo-root",
                        str(root),
                    ]
                )
                == 1
            )

    def test_verify_budgets_flags_oversized_pinned_model_overlay(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_fixture_repo(root)
            assert compiler.main(["generate", "--repo-root", str(root)]) == 0
            overlay_path = root / "home/pinned-overlay.md"
            overlay_path.write_text("x" * 3000, encoding="utf-8")
            manifest_path = root / compiler.MANIFEST_PATH
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["rules"][0]["disposition"] = "pinned-model-overlay"
            manifest["rules"][0]["consumer"] = "home/pinned-overlay.md"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            assert (
                compiler.main(
                    [
                        "verify-budgets",
                        "--core-max-bytes",
                        "999999",
                        "--overlay-max-bytes",
                        "2048",
                        "--skill-max-bytes",
                        "8192",
                        "--description-total-max-bytes",
                        "4096",
                        "--repo-root",
                        str(root),
                    ]
                )
                == 1
            )

    def test_verify_budgets_reports_real_core_overage(self):
        assert (
            compiler.main(
                [
                    "verify-budgets",
                    "--core-max-bytes",
                    "6144",
                    "--overlay-max-bytes",
                    "2048",
                    "--skill-max-bytes",
                    "8192",
                    "--description-total-max-bytes",
                    "4096",
                    "--repo-root",
                    str(REPO),
                ]
            )
            == 1
        )

    def test_verify_budgets_passes_on_small_fixture(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_fixture_repo(root)
            assert (
                compiler.main(
                    [
                        "verify-budgets",
                        "--core-max-bytes",
                        "6144",
                        "--overlay-max-bytes",
                        "2048",
                        "--skill-max-bytes",
                        "8192",
                        "--description-total-max-bytes",
                        "4096",
                        "--repo-root",
                        str(root),
                    ]
                )
                == 0
            )

    def test_audit_coverage_passes_when_every_heading_is_disposed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_fixture_repo(root)
            assert compiler.main(["generate", "--repo-root", str(root)]) == 0
            assert (
                compiler.main(
                    [
                        "audit-coverage",
                        "--legacy",
                        str(compiler.LEGACY_PATH),
                        "--manifest",
                        str(compiler.MANIFEST_PATH),
                        "--repo-root",
                        str(root),
                    ]
                )
                == 0
            )

    def test_split_rule_survives_repeated_generate_after_core_shrinks(self):
        """Regression: a Stage 2 split must not let a rule vanish once core no longer contains its heading."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sop_text = """# Standard Operating Procedures

---

## 0. Binding Contract

Body zero.

## 1. Purpose

Body one.

## 2. Truth

Body two.
"""
            _write_fixture_repo(root, sop_text=sop_text)
            (root / "home/exact_dot_agents/exact_skills/exact_k-x").mkdir(parents=True)
            skill_path = root / "home/exact_dot_agents/exact_skills/exact_k-x/readonly_SKILL.md"
            skill_path.write_text("---\nname: k-x\ndescription: x\n---\n\nmoved content\n", encoding="utf-8")

            dispositions_path = root / ir.DISPOSITIONS_PATH
            dispositions_path.parent.mkdir(parents=True, exist_ok=True)
            dispositions_path.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "overrides": {
                            "sop.1.purpose": {
                                "disposition": "skill",
                                "consumer": "home/exact_dot_agents/exact_skills/exact_k-x/readonly_SKILL.md",
                                "risk_tier": "standard",
                                "eval_ref": "sop.1.purpose.ablation-passed",
                                "text": "## 1. Purpose\n\nBody one.\n\n",
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )
            ablations_path = root / compiler.ABLATIONS_PATH
            ablations_path.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "ablations": {
                            "sop.1.purpose": _passed_ablation(
                                root,
                                "sop.1.purpose",
                                "home/exact_dot_agents/exact_skills/exact_k-x/readonly_SKILL.md",
                            )
                        },
                    }
                ),
                encoding="utf-8",
            )

            assert compiler.main(["generate", "--repo-root", str(root)]) == 0
            legacy_path = root / compiler.LEGACY_PATH
            assert "## 1. Purpose" not in legacy_path.read_text(encoding="utf-8")

            # Second generate re-parses the now-shrunk legacy file; the middle split rule must
            # still appear in original order, sourced from its frozen disposition-override text.
            assert compiler.main(["generate", "--repo-root", str(root)]) == 0
            manifest = json.loads((root / compiler.MANIFEST_PATH).read_text(encoding="utf-8"))
            ids = [r["id"] for r in manifest["rules"]]
            assert ids == ["sop.0.binding-contract", "sop.1.purpose", "sop.2.truth"]
            assert compiler.main(["verify", "--all-targets", "--repo-root", str(root)]) == 0

            assert (
                compiler.main(
                    [
                        "audit-coverage",
                        "--legacy",
                        str(compiler.LEGACY_PATH),
                        "--manifest",
                        str(compiler.MANIFEST_PATH),
                        "--repo-root",
                        str(root),
                    ]
                )
                == 0
            )

    def test_generate_rejects_wrong_frozen_text_for_present_override(self):
        """A first split must freeze the exact source text before removing it from core."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_fixture_repo(root)
            (root / "home/exact_dot_agents/exact_skills/exact_k-x").mkdir(parents=True)
            (root / "home/exact_dot_agents/exact_skills/exact_k-x/readonly_SKILL.md").write_text(
                "---\nname: k-x\ndescription: x\n---\n\nmoved content\n", encoding="utf-8"
            )
            dispositions_path = root / ir.DISPOSITIONS_PATH
            dispositions_path.parent.mkdir(parents=True, exist_ok=True)
            dispositions_path.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "overrides": {
                            "sop.1.purpose": {
                                "disposition": "skill",
                                "consumer": "home/exact_dot_agents/exact_skills/exact_k-x/readonly_SKILL.md",
                                "risk_tier": "standard",
                                "eval_ref": "sop.1.purpose.ablation-passed",
                                "text": "## 1. Purpose\n\nWRONG FROZEN TEXT\n",
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )
            assert compiler.main(["generate", "--repo-root", str(root)]) == 1

    def test_audit_coverage_catches_rule_deleted_after_core_shrinks(self):
        """Regression: deleting a split rule from the manifest must fail coverage even though
        the shrunk legacy file no longer mentions it either."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_fixture_repo(root)
            (root / "home/exact_dot_agents/exact_skills/exact_k-x").mkdir(parents=True)
            (root / "home/exact_dot_agents/exact_skills/exact_k-x/readonly_SKILL.md").write_text(
                "---\nname: k-x\ndescription: x\n---\n\nmoved content\n", encoding="utf-8"
            )
            dispositions_path = root / ir.DISPOSITIONS_PATH
            dispositions_path.parent.mkdir(parents=True, exist_ok=True)
            dispositions_path.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "overrides": {
                            "sop.1.purpose": {
                                "disposition": "skill",
                                "consumer": "home/exact_dot_agents/exact_skills/exact_k-x/readonly_SKILL.md",
                                "risk_tier": "standard",
                                "eval_ref": "sop.1.purpose.ablation-passed",
                                "text": "## 1. Purpose\n\nBody one.\n",
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )
            (root / compiler.ABLATIONS_PATH).write_text(
                json.dumps(
                    {
                        "version": 1,
                        "ablations": {
                            "sop.1.purpose": _passed_ablation(
                                root,
                                "sop.1.purpose",
                                "home/exact_dot_agents/exact_skills/exact_k-x/readonly_SKILL.md",
                            )
                        },
                    }
                ),
                encoding="utf-8",
            )
            assert compiler.main(["generate", "--repo-root", str(root)]) == 0

            manifest_path = root / compiler.MANIFEST_PATH
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["rules"] = [r for r in manifest["rules"] if r["id"] != "sop.1.purpose"]
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            assert (
                compiler.main(
                    [
                        "audit-coverage",
                        "--legacy",
                        str(compiler.LEGACY_PATH),
                        "--manifest",
                        str(compiler.MANIFEST_PATH),
                        "--repo-root",
                        str(root),
                    ]
                )
                == 1
            )

    def test_audit_coverage_catches_simultaneous_legacy_and_bookkeeping_tamper(self):
        """Regression: audit-coverage must not be safe only because Makefile ordering runs
        verify first. Deleting a rule from the legacy file, inventory, and manifest all at
        once must still fail audit-coverage run standalone."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_fixture_repo(root)
            assert compiler.main(["generate", "--repo-root", str(root)]) == 0

            base_inventory_path = root / "base-inventory.json"
            base_inventory_path.write_text(
                (root / ir.RULE_INVENTORY_PATH).read_text(encoding="utf-8"), encoding="utf-8"
            )

            legacy_path = root / compiler.LEGACY_PATH
            tampered = legacy_path.read_text(encoding="utf-8").replace("## 1. Purpose\n\nBody one.\n", "")
            legacy_path.write_text(tampered, encoding="utf-8")

            assert compiler.main(["generate", "--repo-root", str(root)]) == 0

            inventory_path = root / ir.RULE_INVENTORY_PATH
            inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
            inventory["rule_ids"] = [r for r in inventory["rule_ids"] if r != "sop.1.purpose"]
            inventory_path.write_text(json.dumps(inventory), encoding="utf-8")

            assert (
                compiler.main(
                    [
                        "audit-coverage",
                        "--legacy",
                        str(compiler.LEGACY_PATH),
                        "--manifest",
                        str(compiler.MANIFEST_PATH),
                        "--repo-root",
                        str(root),
                        "--base-inventory",
                        str(base_inventory_path),
                    ]
                )
                == 1
            )

    def test_audit_coverage_falls_back_to_base_legacy_when_base_inventory_is_absent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_fixture_repo(root)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.name", "Policy Test"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.email", "policy-test@example.invalid"], cwd=root, check=True)
            subprocess.run(["git", "config", "commit.gpgsign", "false"], cwd=root, check=True)
            subprocess.run(["git", "add", "."], cwd=root, check=True)
            subprocess.run(["git", "commit", "-qm", "base-without-inventory"], cwd=root, check=True)

            legacy_path = root / compiler.LEGACY_PATH
            tampered = legacy_path.read_text(encoding="utf-8").replace("## 1. Purpose\n\nBody one.\n", "")
            legacy_path.write_text(tampered, encoding="utf-8")
            assert compiler.main(["generate", "--repo-root", str(root)]) == 0
            assert (
                compiler.main(
                    [
                        "audit-coverage",
                        "--legacy",
                        str(compiler.LEGACY_PATH),
                        "--manifest",
                        str(compiler.MANIFEST_PATH),
                        "--repo-root",
                        str(root),
                        "--base-ref",
                        "HEAD",
                    ]
                )
                == 1
            )

    def test_audit_coverage_rejects_removed_protected_rule_even_when_hash_listed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_fixture_repo(root)
            base_rules = {rule.id: rule for rule in ir.split_legacy_sop((root / compiler.LEGACY_PATH).read_text())}
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.name", "Policy Test"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.email", "policy-test@example.invalid"], cwd=root, check=True)
            subprocess.run(["git", "config", "commit.gpgsign", "false"], cwd=root, check=True)
            subprocess.run(["git", "add", "."], cwd=root, check=True)
            subprocess.run(["git", "commit", "-qm", "base-without-inventory"], cwd=root, check=True)

            legacy_path = root / compiler.LEGACY_PATH
            legacy_path.write_text("## 1. Purpose\n\nBody one.\n", encoding="utf-8")
            assert compiler.main(["generate", "--repo-root", str(root)]) == 0
            inventory_path = root / ir.RULE_INVENTORY_PATH
            inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
            inventory["removed_rule_sha256"] = [base_rules["sop.0.binding-contract"].sha256]
            inventory_path.write_text(json.dumps(inventory), encoding="utf-8")
            assert (
                compiler.main(
                    [
                        "audit-coverage",
                        "--legacy",
                        str(compiler.LEGACY_PATH),
                        "--manifest",
                        str(compiler.MANIFEST_PATH),
                        "--repo-root",
                        str(root),
                        "--base-ref",
                        "HEAD",
                    ]
                )
                == 1
            )

    def test_audit_coverage_catches_base_ref_inventory_removal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_fixture_repo(root)
            assert compiler.main(["generate", "--repo-root", str(root)]) == 0
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.name", "Policy Test"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.email", "policy-test@example.invalid"], cwd=root, check=True)
            subprocess.run(["git", "config", "commit.gpgsign", "false"], cwd=root, check=True)
            subprocess.run(["git", "add", "."], cwd=root, check=True)
            subprocess.run(["git", "commit", "-qm", "base"], cwd=root, check=True)

            legacy_path = root / compiler.LEGACY_PATH
            tampered = legacy_path.read_text(encoding="utf-8").replace("## 1. Purpose\n\nBody one.\n", "")
            legacy_path.write_text(tampered, encoding="utf-8")
            assert compiler.main(["generate", "--repo-root", str(root)]) == 0
            inventory_path = root / ir.RULE_INVENTORY_PATH
            inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
            inventory["rule_ids"] = [r for r in inventory["rule_ids"] if r != "sop.1.purpose"]
            inventory_path.write_text(json.dumps(inventory), encoding="utf-8")

            assert (
                compiler.main(
                    [
                        "audit-coverage",
                        "--legacy",
                        str(compiler.LEGACY_PATH),
                        "--manifest",
                        str(compiler.MANIFEST_PATH),
                        "--repo-root",
                        str(root),
                        "--base-ref",
                        "HEAD",
                    ]
                )
                == 1
            )

    def test_audit_coverage_catches_duplicate_rule_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_fixture_repo(root)
            assert compiler.main(["generate", "--repo-root", str(root)]) == 0
            manifest_path = root / compiler.MANIFEST_PATH
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            duplicate = dict(manifest["rules"][0])
            manifest["rules"].append(duplicate)
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            assert (
                compiler.main(
                    [
                        "audit-coverage",
                        "--legacy",
                        str(compiler.LEGACY_PATH),
                        "--manifest",
                        str(compiler.MANIFEST_PATH),
                        "--repo-root",
                        str(root),
                    ]
                )
                == 1
            )

    def test_audit_coverage_verifies_the_supplied_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_fixture_repo(root)
            assert compiler.main(["generate", "--repo-root", str(root)]) == 0
            custom_manifest = root / "custom-manifest.json"
            manifest = json.loads((root / compiler.MANIFEST_PATH).read_text(encoding="utf-8"))
            manifest["output_sha256"] = "bad"
            custom_manifest.write_text(json.dumps(manifest), encoding="utf-8")
            assert (
                compiler.main(
                    [
                        "audit-coverage",
                        "--legacy",
                        str(compiler.LEGACY_PATH),
                        "--manifest",
                        str(custom_manifest),
                        "--repo-root",
                        str(root),
                    ]
                )
                == 1
            )

    def test_verify_catches_extra_manifest_rule_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_fixture_repo(root)
            assert compiler.main(["generate", "--repo-root", str(root)]) == 0
            manifest_path = root / compiler.MANIFEST_PATH
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            phantom = dict(manifest["rules"][0])
            phantom["id"] = "sop.999.phantom"
            manifest["rules"].append(phantom)
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            assert compiler.main(["verify", "--all-targets", "--repo-root", str(root)]) == 1

    def test_verify_catches_stale_manifest_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_fixture_repo(root)
            assert compiler.main(["generate", "--repo-root", str(root)]) == 0
            manifest_path = root / compiler.MANIFEST_PATH
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["rules"][0]["risk_tier"] = "bogus-risk-tier"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            assert compiler.main(["verify", "--all-targets", "--repo-root", str(root)]) == 1

    def test_audit_coverage_catches_manifest_rule_missing_from_inventory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_fixture_repo(root)
            assert compiler.main(["generate", "--repo-root", str(root)]) == 0
            manifest_path = root / compiler.MANIFEST_PATH
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            phantom = dict(manifest["rules"][0])
            phantom["id"] = "sop.999.phantom"
            manifest["rules"].append(phantom)
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            inventory_path = root / ir.RULE_INVENTORY_PATH
            inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
            inventory["rule_ids"].append("sop.999.phantom")
            inventory_path.write_text(json.dumps(inventory), encoding="utf-8")
            assert compiler.main(["verify", "--all-targets", "--repo-root", str(root)]) == 1

            inventory["rule_ids"] = [r for r in inventory["rule_ids"] if r != "sop.999.phantom"]
            manifest["rules"] = [r for r in manifest["rules"] if r["id"] != "sop.999.phantom"]
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            inventory_path.write_text(json.dumps(inventory), encoding="utf-8")

            manifest["rules"].append(phantom)
            manifest["output_sha256"] = compiler._sha256_bytes(ir.render(ir.load_legacy_sop(root)).encode("utf-8"))
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            assert (
                compiler.main(
                    [
                        "audit-coverage",
                        "--legacy",
                        str(compiler.LEGACY_PATH),
                        "--manifest",
                        str(compiler.MANIFEST_PATH),
                        "--repo-root",
                        str(root),
                    ]
                )
                == 1
            )

    def test_audit_coverage_catches_uncovered_heading(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_fixture_repo(root)
            assert compiler.main(["generate", "--repo-root", str(root)]) == 0
            manifest_path = root / compiler.MANIFEST_PATH
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["rules"].pop()
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            assert (
                compiler.main(
                    [
                        "audit-coverage",
                        "--legacy",
                        str(compiler.LEGACY_PATH),
                        "--manifest",
                        str(compiler.MANIFEST_PATH),
                        "--repo-root",
                        str(root),
                    ]
                )
                == 1
            )

    def test_audit_coverage_catches_missing_eval_ref(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_fixture_repo(root)
            assert compiler.main(["generate", "--repo-root", str(root)]) == 0
            manifest_path = root / compiler.MANIFEST_PATH
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["rules"][0]["eval_ref"] = ""
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            assert (
                compiler.main(
                    [
                        "audit-coverage",
                        "--legacy",
                        str(compiler.LEGACY_PATH),
                        "--manifest",
                        str(compiler.MANIFEST_PATH),
                        "--repo-root",
                        str(root),
                    ]
                )
                == 1
            )

    def test_audit_coverage_rejects_retirement_without_passing_ablation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_fixture_repo(root)
            assert compiler.main(["generate", "--repo-root", str(root)]) == 0
            manifest_path = root / compiler.MANIFEST_PATH
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["rules"][0]["disposition"] = "retired-by-passing-ablation"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            assert (
                compiler.main(
                    [
                        "audit-coverage",
                        "--legacy",
                        str(compiler.LEGACY_PATH),
                        "--manifest",
                        str(compiler.MANIFEST_PATH),
                        "--repo-root",
                        str(root),
                    ]
                )
                == 1
            )

    def test_audit_coverage_rejects_non_core_binding_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_fixture_repo(root)
            (root / "home/exact_dot_agents/exact_skills/exact_k-x").mkdir(parents=True)
            (root / "home/exact_dot_agents/exact_skills/exact_k-x/readonly_SKILL.md").write_text(
                "---\nname: k-x\ndescription: x\n---\n\nmoved content\n", encoding="utf-8"
            )
            (root / ir.DISPOSITIONS_PATH).write_text(
                json.dumps(
                    {
                        "version": 1,
                        "overrides": {
                            "sop.0.binding-contract": {
                                "disposition": "skill",
                                "consumer": "home/exact_dot_agents/exact_skills/exact_k-x/readonly_SKILL.md",
                                "risk_tier": "standard",
                                "eval_ref": "sop.0.binding-contract.ablation-passed",
                                "text": "# Standard Operating Procedures\n\n---\n\n## 0. Binding Contract\n\nBody zero.\n\n",
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )
            (root / compiler.ABLATIONS_PATH).write_text(
                json.dumps(
                    {
                        "version": 1,
                        "ablations": {
                            "sop.0.binding-contract": _passed_ablation(
                                root,
                                "sop.0.binding-contract",
                                "home/exact_dot_agents/exact_skills/exact_k-x/readonly_SKILL.md",
                            )
                        },
                    }
                ),
                encoding="utf-8",
            )
            assert compiler.main(["generate", "--repo-root", str(root)]) == 0
            assert (
                compiler.main(
                    [
                        "audit-coverage",
                        "--legacy",
                        str(compiler.LEGACY_PATH),
                        "--manifest",
                        str(compiler.MANIFEST_PATH),
                        "--repo-root",
                        str(root),
                    ]
                )
                == 1
            )

    def test_audit_coverage_rejects_non_core_protected_lifecycle_rule(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            protected_sop = """# Standard Operating Procedures

---

## 0. Binding Contract

Body zero.

### 3.2 Ownership Gate

Ownership body.
"""
            _write_fixture_repo(root, sop_text=protected_sop)
            (root / "home/exact_dot_agents/exact_skills/exact_k-x").mkdir(parents=True)
            (root / "home/exact_dot_agents/exact_skills/exact_k-x/readonly_SKILL.md").write_text(
                "---\nname: k-x\ndescription: x\n---\n\nmoved content\n", encoding="utf-8"
            )
            (root / ir.DISPOSITIONS_PATH).write_text(
                json.dumps(
                    {
                        "version": 1,
                        "overrides": {
                            "sop.3.2.ownership-gate": {
                                "disposition": "skill",
                                "consumer": "home/exact_dot_agents/exact_skills/exact_k-x/readonly_SKILL.md",
                                "risk_tier": "ownership",
                                "eval_ref": "sop.3.2.ownership-gate.ablation-passed",
                                "text": "### 3.2 Ownership Gate\n\nOwnership body.\n",
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )
            (root / compiler.ABLATIONS_PATH).write_text(
                json.dumps(
                    {
                        "version": 1,
                        "ablations": {
                            "sop.3.2.ownership-gate": _passed_ablation(
                                root,
                                "sop.3.2.ownership-gate",
                                "home/exact_dot_agents/exact_skills/exact_k-x/readonly_SKILL.md",
                            )
                        },
                    }
                ),
                encoding="utf-8",
            )
            assert compiler.main(["generate", "--repo-root", str(root)]) == 0
            assert (
                compiler.main(
                    [
                        "audit-coverage",
                        "--legacy",
                        str(compiler.LEGACY_PATH),
                        "--manifest",
                        str(compiler.MANIFEST_PATH),
                        "--repo-root",
                        str(root),
                    ]
                )
                == 1
            )

    def test_audit_coverage_rejects_ablation_metadata_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_fixture_repo(root)
            (root / "home/exact_dot_agents/exact_skills/exact_k-x").mkdir(parents=True)
            (root / "home/exact_dot_agents/exact_skills/exact_k-x/readonly_SKILL.md").write_text(
                "---\nname: k-x\ndescription: x\n---\n\nmoved content\n", encoding="utf-8"
            )
            (root / ir.DISPOSITIONS_PATH).write_text(
                json.dumps(
                    {
                        "version": 1,
                        "overrides": {
                            "sop.1.purpose": {
                                "disposition": "skill",
                                "consumer": "home/exact_dot_agents/exact_skills/exact_k-x/readonly_SKILL.md",
                                "risk_tier": "standard",
                                "eval_ref": "sop.1.purpose.ablation-passed",
                                "text": "## 1. Purpose\n\nBody one.\n",
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )
            (root / compiler.ABLATIONS_PATH).write_text(
                json.dumps(
                    {
                        "version": 1,
                        "ablations": {
                            "sop.1.purpose": {
                                "status": "passed",
                                "target_disposition": "skill",
                                "consumer": "wrong.md",
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )
            assert compiler.main(["generate", "--repo-root", str(root)]) == 0
            assert (
                compiler.main(
                    [
                        "audit-coverage",
                        "--legacy",
                        str(compiler.LEGACY_PATH),
                        "--manifest",
                        str(compiler.MANIFEST_PATH),
                        "--repo-root",
                        str(root),
                    ]
                )
                == 1
            )

    def test_explain_returns_full_rule_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_fixture_repo(root)
            import contextlib
            import io

            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = compiler.main(["explain", "sop.0.binding-contract", "--repo-root", str(root)])
            assert code == 0
            record = json.loads(out.getvalue())
            assert record["id"] == "sop.0.binding-contract"
            assert record["disposition"] == "core"
            assert "Body zero" in record["text"]

    def test_explain_unknown_rule_id_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_fixture_repo(root)
            assert compiler.main(["explain", "sop.nonexistent", "--repo-root", str(root)]) == 1

    def test_measure_reports_repo_controlled_bytes_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_fixture_repo(root)
            import contextlib
            import io

            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = compiler.main(["measure", "--repo-root", str(root)])
            assert code == 0
            report = json.loads(out.getvalue())
            assert report["repo_controlled_bytes"]["core_sop"] == len(FIXTURE_SOP.encode("utf-8"))
            assert "harness-owned system prompt" in report["uncontrolled_unknown"]

    def test_committed_policy_artifacts_are_verified_read_only(self):
        """The real repo policy check must not repair stale generated artifacts."""
        assert compiler.main(["verify", "--all-targets", "--repo-root", str(REPO)]) == 0


class EvalScaffoldTest(unittest.TestCase):
    """WHEN checking live-eval scaffolding without issuing live requests."""

    def _capture_json(self, fn, args):
        import contextlib
        import io

        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = fn(args)
        return code, json.loads(out.getvalue())

    def test_plan_reports_cross_product_without_authorized_spend(self):
        matrix = REPO / "scripts/tests/fixtures/ai_policy_eval/matrix.yaml"
        code, report = self._capture_json(
            evals.main,
            [
                "plan",
                "--matrix",
                str(matrix),
                "--manifest",
                str(REPO / compiler.MANIFEST_PATH),
                "--capabilities",
                str(REPO / capabilities.SNAPSHOT_PATH),
            ],
        )
        assert code == 0
        assert report["cell_count"] == 4992
        assert report["estimated_requests"] == 4992
        assert report["estimated_input_tokens"] == 19_968_000
        assert report["estimated_output_tokens"] == 4_992_000
        assert report["estimated_total_tokens"] == 24_960_000
        assert report["unsupported_cell_count"] == 1152
        assert "unsupported_cells" not in report
        # Codex, Copilot and Gemini left this list once their subagents got pinned models in
        # config.toml / settings.json / agents.overrides; Cursor has no home-level agent files.
        expected_unsupported = [
            {
                "reason": "subagent_model_binding is 'runtime', not 'static'",
                "harness": harness,
                "agent_role": "subagent-static-pinned",
                "count": 384,
            }
            for harness in ("cursor", "generic", "opencode")
        ]
        assert report["unsupported_summary"] == expected_unsupported
        assert sum(item["count"] for item in report["unsupported_summary"]) == report["unsupported_cell_count"]
        assert report["risk_tiers"]["scenario_counts"]["standard"] == 69
        assert report["risk_tiers"]["cell_counts"]["safety"] == 312
        assert report["risk_tiers"]["unknown_rule_ids"] == []
        assert report["max_authorized_spend"] is None
        assert report["authorization_status"].startswith("not authorized")

    def test_verify_modes_report_blocked_without_live_requests(self):
        matrix = REPO / "scripts/tests/fixtures/ai_policy_eval/matrix.yaml"
        for command in (
            [
                "verify-routing",
                "--matrix",
                str(matrix),
                "--runs-root",
                "/tmp/no-runs",
                "--capabilities",
                str(REPO / capabilities.SNAPSHOT_PATH),
            ],
            [
                "verify-behavior",
                "--baseline-ref",
                "origin/main",
                "--candidate-ref",
                "HEAD",
                "--matrix",
                str(matrix),
                "--runs-root",
                "/tmp/no-runs",
                "--capabilities",
                str(REPO / capabilities.SNAPSHOT_PATH),
            ],
        ):
            code, report = self._capture_json(evals.main, command)
            assert code == 2
            assert report["unblocked_count"] == 0
            assert report["blocked_count"] == 4992
            assert report["unsupported_cell_count"] == 1152
            assert sum(item["count"] for item in report["unsupported_summary"]) == 1152
            assert {cell["status"] for cell in report["cells"]} == {"blocked"}
            assert {cell["repetition"] for cell in report["cells"]} == {1}

    def test_eval_matrix_has_three_scenarios_for_every_manifest_rule(self):
        matrix = evals._load_matrix(REPO / "scripts/tests/fixtures/ai_policy_eval/matrix.yaml")
        manifest = json.loads((REPO / compiler.MANIFEST_PATH).read_text(encoding="utf-8"))
        scenarios = set(matrix["scenarios"])
        for record in manifest["rules"]:
            for suffix in ("positive", "negative-control", "malformed-input"):
                assert f"{record['id']}.{suffix}" in scenarios
        assert len(scenarios) == len(manifest["rules"]) * 3


if __name__ == "__main__":
    unittest.main()
