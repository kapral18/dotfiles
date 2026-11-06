from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from _test_support import REPO

CHEZMOI = shutil.which("chezmoi")


@unittest.skipUnless(CHEZMOI, "chezmoi is not installed")
class PackageRecoveryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="package-recovery-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / "repo/home"
        shutil.copytree(REPO / "home", self.source, symlinks=True)
        shutil.copytree(REPO / "scripts", self.root / "repo/scripts", ignore=shutil.ignore_patterns("__pycache__"))
        self.home = self.root / "home"
        self.home.mkdir()
        self.bin = self.root / "bin"
        self.bin.mkdir()
        config = self.root / "chezmoi.toml"
        config.touch()
        self.command = [
            CHEZMOI,
            "--config",
            str(config),
            "--source",
            str(self.source),
            "--destination",
            str(self.home),
            "--persistent-state",
            str(self.root / "state.db"),
        ]
        self.env = {
            "HOME": str(self.home),
            "PATH": f"{self.bin}:{Path(sys.executable).parent}:{os.defpath}",
            "TMPDIR": str(self.root),
            "XDG_STATE_HOME": str(self.root / "state"),
            "CHEZMOI_ARTIFACT_LEDGER": str(self.root / "ledger.json"),
        }
        self.fake("chezmoi", "#!/bin/sh\nexec " + shlex.join(self.command) + ' "$@"\n')

    def fake(self, name, source):
        target = self.bin / name
        target.write_text(source)
        target.chmod(0o755)

    def render(self, text, *arguments):
        return subprocess.run(
            [*self.command, "execute-template", *arguments],
            input=text,
            text=True,
            capture_output=True,
            env=self.env,
            cwd=self.root,
            timeout=10,
            check=True,
        ).stdout

    def hook(self, name):
        text = (self.source / ".chezmoiscripts" / name).read_text()
        return subprocess.run(
            ["/bin/bash"],
            input=self.render(text),
            text=True,
            capture_output=True,
            env=self.env,
            cwd=self.root,
            timeout=15,
        )

    def test_bootstrap_scripts_inherit_architecture_specific_homebrew_path(self):
        template = (self.source / ".chezmoi.toml.tmpl").read_text()
        prompts = [
            "--init",
            "--promptBool",
            "Is 1Password ready? y/N=true",
            "--promptBool",
            "Download llama.cpp models on apply? y/N=false",
            "--promptString",
            "Enter your primary email*: =fixture@example.invalid",
            "--promptString",
            "Enter your primary public SSH key*: =ssh-ed25519 fixture",
            "--promptString",
            "Select Cache TTL for PGP config in sec:=86400",
        ]
        for arch, prefix in [("arm64", "/opt/homebrew"), ("amd64", "/usr/local")]:
            with self.subTest(arch=arch):
                output = self.render(template.replace(".chezmoi.arch", json.dumps(arch)), *prompts)
                rendered_config = self.root / "rendered.toml"
                rendered_config.write_text(output)
                config = json.loads(
                    subprocess.run(
                        [*self.command, "--config", str(rendered_config), "dump-config", "--format=json"],
                        capture_output=True,
                        text=True,
                        env=self.env,
                        cwd=self.root,
                        timeout=10,
                        check=True,
                    ).stdout
                )
                self.assertEqual(config["scriptEnv"]["PATH"], f"{prefix}/bin:{prefix}/sbin:{self.env['PATH']}")
                self.assertEqual(config["data"]["homebrewPrefix"], prefix)

    def test_only_apple_silicon_receives_the_metal_sd_cli_archive(self):
        template = (self.source / "readonly_dot_default-custom-packages.tmpl").read_text()
        for arch, expected in [("arm64", True), ("amd64", False)]:
            with self.subTest(arch=arch):
                rendered = self.render(
                    template.replace(".chezmoi.arch", json.dumps(arch)).replace(".chezmoi.os", '"darwin"')
                )
                rows = [line for line in rendered.splitlines() if line.startswith("zip_opt|sd-cli|")]
                self.assertEqual(bool(rows), expected)

    def test_uv_final_declaration_survives_eof_and_empty_lists_prune_installed_tools(self):
        declaration = self.source / "readonly_dot_default-uv-tools.tmpl"
        declaration.write_text("ruff")
        installed = self.root / "uv.json"
        installed.write_text(json.dumps(["ruff", "black"]))
        self.env["UV_STATE"] = str(installed)
        self.fake(
            "uv",
            f'#!{sys.executable}\nimport json,os,sys\nfrom pathlib import Path\np=Path(os.environ["UV_STATE"])\nnames=json.loads(p.read_text())\nif sys.argv[1:] == ["tool","list"]:\n print("\\n".join(name+" v1" for name in names))\nelif sys.argv[1:3] == ["tool","uninstall"]:\n names.remove(sys.argv[3]); p.write_text(json.dumps(names))\nelse:\n raise SystemExit(9)\n',
        )
        result = self.hook("run_onchange_after_06-update-uv-tools.sh.tmpl")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(installed.read_text()), ["ruff"])

        declaration.write_text("# no declared tools\n")
        result = self.hook("run_onchange_after_06-update-uv-tools.sh.tmpl")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(installed.read_text()), [])

        installed.write_text(json.dumps(["black"]))
        declaration.write_text("")
        result = self.hook("run_onchange_after_06-update-uv-tools.sh.tmpl")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(installed.read_text()), [])

    def test_go_install_ownership_survives_later_failure_and_retry(self):
        declaration = self.source / "readonly_dot_default-golang-pkgs.tmpl"
        declaration.write_text("example.invalid/first\nexample.invalid/fail\n")
        gobin = self.root / "gobin"
        gobin.mkdir()
        self.env["FIXTURE_GOBIN"] = str(gobin)
        self.fake(
            "go",
            f'#!{sys.executable}\nimport os,sys\nfrom pathlib import Path\nargs=sys.argv[1:]\nif args == ["env","GOBIN"]: print(os.environ["FIXTURE_GOBIN"])\nelif args[0] == "install":\n name=args[1].split("@",1)[0].rsplit("/",1)[-1]\n if name == "fail": raise SystemExit(7)\n Path(os.environ["FIXTURE_GOBIN"],name).write_text("installed")\nelse: raise SystemExit(9)\n',
        )
        name = "run_onchange_after_05-update-golang-pkgs.sh.tmpl"
        first = self.hook(name)
        self.assertNotEqual(first.returncode, 0)
        self.assertTrue((gobin / "first").is_file(), first.stdout + first.stderr)
        state = self.home / ".cache/chezmoi/golang-pkgs-state"
        self.assertTrue(state.is_file(), "successful install must be owned before a later package fails")
        self.assertIn("example.invalid/first", state.read_text().splitlines())
        declaration.write_text("example.invalid/first\n")
        retry = self.hook(name)
        self.assertEqual(retry.returncode, 0, retry.stdout + retry.stderr)
        declaration.write_text("")
        cleanup = self.hook(name)
        self.assertEqual(cleanup.returncode, 0, cleanup.stdout + cleanup.stderr)
        self.assertFalse((gobin / "first").exists())

    def test_generated_configs_report_owning_hook_drift(self):
        import generated_artifact_ledger as ledger

        names = [
            "07-merge-codex-config",
            "07-generate-mcp-configs",
            "07-merge-claude-global-config",
            "07-merge-pi-config",
        ]
        for name in names:
            filename = f"run_onchange_after_{name}.sh.tmpl"
            result = self.hook(filename)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            rows = [
                row
                for row in ledger.load_ledger(Path(self.env["CHEZMOI_ARTIFACT_LEDGER"]))["artifacts"].values()
                if row["producer"] == name
            ]
            self.assertTrue(rows, name)
            self.assertTrue(all("transform-drift" not in ledger.evaluate_artifact(row)["reasons"] for row in rows))
            hook = self.source / ".chezmoiscripts" / filename
            hook.write_text(hook.read_text() + "\nexit 9\n")
            for row in rows:
                self.assertIn("transform-drift", ledger.evaluate_artifact(row)["reasons"], row["artifact_id"])


if __name__ == "__main__":
    unittest.main()
