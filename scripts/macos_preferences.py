#!/usr/bin/env python3
"""Update Finder icon views through defaults, preserving unrelated preferences.

Usage: python3 scripts/macos_preferences.py DOMAIN
Tests use an absolute temporary domain, never the user's Finder preferences.
"""

from __future__ import annotations

import argparse
import plistlib
import subprocess


def configure_finder_icon_views(domain: str) -> None:
    exported = subprocess.run(["/usr/bin/defaults", "export", domain, "-"], capture_output=True, check=True)
    preferences = plistlib.loads(exported.stdout)
    updates = {}
    for name in ("DesktopViewSettings", "FK_StandardViewSettings", "StandardViewSettings"):
        view = preferences.get(name, {})
        icons = view.setdefault("IconViewSettings", {})
        icons.update(arrangeBy="grid", gridSpacing=54.0, iconSize=64.0, showItemInfo=True)
        if name == "DesktopViewSettings":
            icons["labelOnBottom"] = True
        updates[name] = plistlib.dumps(view).decode("utf-8")

    # Prepare every dictionary before writing, so malformed existing data fails
    # without partially updating the other views. Never replace the whole domain.
    for name, value in updates.items():
        subprocess.run(["/usr/bin/defaults", "write", domain, name, value], check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("domain", help="Finder preference domain or absolute test-domain path")
    args = parser.parse_args()
    configure_finder_icon_views(args.domain)


if __name__ == "__main__":
    main()
