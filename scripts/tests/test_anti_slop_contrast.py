"""Exercise the shared contrast CLI against WCAG thresholds, without a browser."""

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "home/exact_dot_agents/exact_skills/exact_k-anti-slop/exact_scripts/readonly_contrast.py"


class ContrastTests(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True, timeout=5)

    def test_WHEN_extreme_or_equal_colors_SHOULD_report_known_ratios(self):
        for foreground, background, ratio in [("#000", "#fff", 21), ("ffffff", "000000", 21), ("#AbC", "#aabbcc", 1)]:
            with self.subTest(foreground=foreground, background=background):
                result = self.run_cli(foreground, background)
                self.assertEqual(result.returncode, 0 if ratio == 21 else 1, result.stderr)
                self.assertEqual(json.loads(result.stdout)["ratio"], ratio)

    def test_WHEN_pair_nears_a_threshold_SHOULD_compare_unrounded_ratio(self):
        # Fixed sRGB pairs straddle the WCAG 3, 4.5 and 7 thresholds. The #777
        # regression is also documented by upstream antislop 3.2.21.
        cases = [
            ("#959595", "#fff", "3", False),
            ("#949494", "#fff", "3", True),
            ("#777", "#070707", "4.5", False),
            ("#767676", "#fff", "4.5", True),
            ("#5a5a5a", "#fff", "7", False),
            ("#595959", "#fff", "7", True),
        ]
        for foreground, background, minimum, passes in cases:
            with self.subTest(foreground=foreground, minimum=minimum):
                result = self.run_cli(foreground, background, "--minimum", minimum)
                data = json.loads(result.stdout)
                self.assertEqual(result.returncode, 0 if passes else 1, result.stderr)
                self.assertEqual(data["passes"], passes)
                self.assertEqual(data["minimum"], float(minimum))

    def test_WHEN_large_text_passes_only_SHOULD_keep_normal_text_failure_visible(self):
        result = self.run_cli("#777", "#fff", "--minimum", "3")
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertFalse(data["aa_normal"])
        self.assertTrue(data["aa_large"])
        self.assertTrue(data["non_text"])
        self.assertFalse(data["aaa_normal"])
        self.assertFalse(data["aaa_large"])
        default = self.run_cli("#777", "#fff")
        self.assertEqual(default.returncode, 1, default.stderr)

    def test_WHEN_color_is_not_opaque_rgb_hex_SHOULD_reject_it(self):
        for color in ["", "##fff", "#1234", "#11223344", "#12", "#ggg", "#１２３", "white", " #fff", "#fff "]:
            with self.subTest(color=color):
                result = self.run_cli(color, "#fff")
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertEqual(result.stdout, "")

    def test_WHEN_arguments_are_missing_or_invalid_SHOULD_not_print_a_result(self):
        for args in [(), ("#fff",), ("#fff", "#000", "--minimum", "4"), ("#fff", "#000", "extra")]:
            with self.subTest(args=args):
                result = self.run_cli(*args)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertEqual(result.stdout, "")


if __name__ == "__main__":
    unittest.main()
