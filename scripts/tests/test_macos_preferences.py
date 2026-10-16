from __future__ import annotations

import plistlib
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "macos_preferences.py"


@unittest.skipUnless(sys.platform == "darwin", "requires the native macOS defaults consumer")
class TestFinderPreferences(unittest.TestCase):
    """WHEN applying icon-view preferences to an isolated defaults domain."""

    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix="finder-preferences-test-")
        self.addCleanup(directory.cleanup)
        # An absolute domain is mandatory: HOME alone does not isolate CFPreferences.
        self.domain = Path(directory.name) / "Finder préférences"

    def seed(self, preferences):
        subprocess.run(
            ["/usr/bin/defaults", "import", str(self.domain), "-"],
            input=plistlib.dumps(preferences),
            capture_output=True,
            check=True,
        )

    def read_preferences(self):
        actual = subprocess.run(
            ["/usr/bin/defaults", "export", str(self.domain), "-"],
            capture_output=True,
            check=True,
        )
        return plistlib.loads(actual.stdout)

    def configure(self):
        return subprocess.run(
            [sys.executable, str(SCRIPT), str(self.domain)], capture_output=True, text=True, check=False
        )

    def test_SHOULD_initialize_missing_view_dictionaries(self):
        self.seed({"Unrelated": "keep"})

        actual = self.configure()

        self.assertEqual(actual.returncode, 0, actual.stderr)
        preferences = self.read_preferences()
        self.assertEqual(preferences["DesktopViewSettings"]["IconViewSettings"]["arrangeBy"], "grid")
        self.assertEqual(preferences["FK_StandardViewSettings"]["IconViewSettings"]["arrangeBy"], "grid")
        self.assertEqual(preferences["StandardViewSettings"]["IconViewSettings"]["arrangeBy"], "grid")
        self.assertIs(preferences["DesktopViewSettings"]["IconViewSettings"]["labelOnBottom"], True)

    def test_SHOULD_preserve_unmanaged_fields_at_every_level(self):
        self.seed(
            {
                "Unrelated": ["keep", "ø"],
                "DesktopViewSettings": {
                    "ViewOption": 42,
                    "IconViewSettings": {"textSize": 13, "arrangeBy": "name", "iconSize": 32.0},
                },
                "StandardViewSettings": {"IconViewSettings": {"labelOnBottom": False}},
            }
        )

        actual = self.configure()

        self.assertEqual(actual.returncode, 0, actual.stderr)
        preferences = self.read_preferences()
        self.assertEqual(preferences["Unrelated"], ["keep", "ø"])
        self.assertEqual(preferences["DesktopViewSettings"]["ViewOption"], 42)
        self.assertEqual(
            preferences["DesktopViewSettings"]["IconViewSettings"],
            {
                "textSize": 13,
                "arrangeBy": "grid",
                "iconSize": 64.0,
                "gridSpacing": 54.0,
                "showItemInfo": True,
                "labelOnBottom": True,
            },
        )
        self.assertIs(preferences["StandardViewSettings"]["IconViewSettings"]["labelOnBottom"], False)

    def test_SHOULD_merge_fresh_user_changes_on_reapply(self):
        self.seed({})
        self.assertEqual(self.configure().returncode, 0)
        preferences = self.read_preferences()
        preferences["DesktopViewSettings"]["IconViewSettings"].update(arrangeBy="name", textSize=17)
        del preferences["FK_StandardViewSettings"]
        preferences["NewPreference"] = "preserve"
        self.seed(preferences)

        actual = self.configure()

        self.assertEqual(actual.returncode, 0, actual.stderr)
        preferences = self.read_preferences()
        self.assertEqual(preferences["DesktopViewSettings"]["IconViewSettings"]["arrangeBy"], "grid")
        self.assertEqual(preferences["DesktopViewSettings"]["IconViewSettings"]["textSize"], 17)
        self.assertEqual(preferences["FK_StandardViewSettings"]["IconViewSettings"]["arrangeBy"], "grid")
        self.assertEqual(preferences["NewPreference"], "preserve")

    def test_SHOULD_leave_all_preferences_unchanged_when_a_later_view_is_malformed(self):
        original = {
            "DesktopViewSettings": {"IconViewSettings": {"arrangeBy": "name"}},
            "StandardViewSettings": {"IconViewSettings": "not a dictionary"},
        }
        self.seed(original)

        actual = self.configure()

        self.assertNotEqual(actual.returncode, 0)
        self.assertEqual(self.read_preferences(), original)


if __name__ == "__main__":
    unittest.main()
