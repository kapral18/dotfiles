from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
HARNESS = Path(__file__).with_name("neovim_config_schemas.lua")


def neovim_binary() -> str | None:
    # Shards replace HOME; resolve mise installations without executing its shim.
    binary = shutil.which(
        "nvim", path=os.pathsep.join(path for path in os.get_exec_path() if Path(path).name != "shims")
    )
    if binary:
        return binary
    shim = shutil.which("nvim")
    if shim and Path(shim).resolve().name == "mise":
        installed = sorted((Path(shim).parent.parent / "installs/neovim").glob("*/bin/nvim"), reverse=True)
        return next((str(path) for path in installed if os.access(path, os.X_OK)), None)
    return None


NVIM = neovim_binary()


@unittest.skipUnless(NVIM, "Neovim is not installed")
class ConfigSchemaTests(unittest.TestCase):
    def run_case(self, case: str) -> None:
        with tempfile.TemporaryDirectory(prefix="config-schemas-") as scratch:
            env = os.environ | {"CONFIG_SCHEMA_TEST_ROOT": str(REPO), "CONFIG_SCHEMA_TEST_TMP": scratch}
            result = subprocess.run(
                [NVIM, "--headless", "-u", "NONE", "-i", "NONE", "-l", str(HARNESS), case],
                env=env,
                text=True,
                capture_output=True,
                timeout=15,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_servers_accept_templates_and_keep_helm_separate(self) -> None:
        self.run_case("servers")

    def test_template_autoformat_preserves_buffer_contents(self) -> None:
        self.run_case("format")


if __name__ == "__main__":
    unittest.main()
