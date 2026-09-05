#!/usr/bin/env python3
"""Read installed Playwriter documentation by audited complete sections, never summaries.

No browser operation or installed-package writes.

Usage: python3 read_docs.py [core|PROFILE ...]
Use core first; operation profiles emit only their own complete sections.
Use --list to inspect available profiles and full-document fallback behavior.
Unknown document versions/hashes emit the complete documentation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

AUDITED_SHA = "b4ecf1df8ae351719000212ce0b97858cfe0ec50ee51ed79d6a441123243e9ef"
AUDITED_VERSION = "0.5.0"
CORE = {
    "CLI Usage",
    "Session management",
    "Execute code",
    "Execute from file",
    "playwriter best practices",
    "context variables",
    "importing local scripts",
    "rules",
    "interaction feedback loop",
    "common mistakes to avoid",
    "accessibility snapshots",
    "choosing between snapshot methods",
    "selector best practices",
    "working with pages",
    "navigation",
    "common patterns",
    "utility functions",
    "getLatestLogs",
    "waitForPageLoad",
    "getCDPSession",
}
GROUPS = {
    "remote": {"Remote access (control browser from another machine)"},
    "direct": {"Direct CDP connection (no extension needed)"},
    "headless": {"Headless browser (no extension, no user browser)"},
    "cloud": {"Cloud browsers (stealth, proxies, CAPTCHA solving)"},
    "recorder": {"Recording user actions for skill generation"},
    "stream": {"Live streaming to RTMP (X Live, Twitch, YouTube)"},
    "debug": {"Debugging playwriter issues"},
    "html": {"getCleanHTML"},
    "markdown": {"getPageMarkdown"},
    "locator": {"getLocatorStringForElement"},
    "react": {"getReactSource", "getReactComponentInfo"},
    "pinned": {"inspectPinnedElement", "pinned elements"},
    "styles": {"getStylesForLocator"},
    "debugger": {"createDebugger"},
    "editor": {"createEditor"},
    "screenshots": {
        "screenshotWithAccessibilityLabels",
        "resizeImageForAgent",
        "taking screenshots",
        "region screenshot (zoom equivalent)",
    },
    "video": {"recording.start / recording.stop", "ghostCursor.show / ghostCursor.hide", "createDemoVideo"},
    "evaluate": {"page.evaluate"},
    "files": {"loading files"},
    "network": {"network interception"},
    "input": {
        "computer use (low-level mouse/keyboard)",
        "clicking",
        "hover",
        "scroll",
        "drag",
        "key hold / release / repeat",
        "resize viewport",
    },
    "ghost": {"Ghost Browser integration"},
}


def sections(raw: bytes) -> list[dict]:
    """Partition every byte; headings inside code fences are ordinary content."""
    lines = raw.decode("utf-8").splitlines(keepends=True)
    starts = []
    fenced = False
    in_utilities = False
    for i, line in enumerate(lines):
        if line.startswith("```"):
            fenced = not fenced
            continue
        if fenced:
            continue
        heading = re.match(r"^#{1,3} (.+?)\s*$", line)
        if heading:
            name = heading.group(1)
            starts.append((i, name))
            in_utilities = name == "utility functions"
        elif in_utilities:
            utility = re.match(r"^\*\*(.+?)\*\* - ", line)
            if utility:
                starts.append((i, utility.group(1)))
    if not starts or starts[0][0] != 0:
        raise ValueError("Unclassified preamble")
    names = [x[1] for x in starts]
    if len(names) != len(set(names)):
        raise ValueError("Duplicate section names")
    result = []
    for pos, (start, name) in enumerate(starts):
        end = starts[pos + 1][0] if pos + 1 < len(starts) else len(lines)
        body = "".join(lines[start:end]).encode()
        result.append(dict(name=name, start_line=start + 1, end_line=end, raw=body))
    if b"".join(x["raw"] for x in result) != raw:
        raise ValueError("Incomplete document partition")
    expected = CORE | set().union(*GROUPS.values())
    if set(names) != expected:
        raise ValueError("Section inventory differs from audited map")
    return result


def select(raw: bytes, groups: list[str], version: str | None = AUDITED_VERSION) -> tuple[bytes, dict]:
    digest = hashlib.sha256(raw).hexdigest()
    if version != AUDITED_VERSION:
        return raw, dict(mode="full-unrecognized-version", version=version, sha256=digest, bytes=len(raw))
    if digest != AUDITED_SHA:
        return raw, dict(mode="full-unrecognized-document", sha256=digest, bytes=len(raw))
    if "full" in groups or "recorder" in groups:
        return raw, dict(mode="full", sha256=digest, bytes=len(raw))
    try:
        chunks = sections(raw)
    except ValueError as error:
        return raw, dict(mode="full-inventory-mismatch", reason=str(error), sha256=digest, bytes=len(raw))
    selected = (CORE if "core" in groups else set()) | set().union(*(GROUPS[g] for g in groups if g != "core"))
    content = b"".join(x["raw"] for x in chunks if x["name"] in selected)
    return content, dict(
        mode="selected-complete-sections",
        sha256=digest,
        bytes=len(content),
        total_bytes=len(raw),
        requires_core="core" not in groups,
        selected=[x["name"] for x in chunks if x["name"] in selected],
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("groups", nargs="*", metavar="PROFILE")
    parser.add_argument("--list", action="store_true", help="List exact operation profiles without calling Playwriter.")
    args = parser.parse_args()
    unknown = set(args.groups) - {"core", "full", *GROUPS}
    if unknown:
        parser.error("unknown profile(s): " + ", ".join(sorted(unknown)))
    if args.list:
        print(
            json.dumps(
                {
                    "core": sorted(CORE),
                    "full": "Entire document; also required for recorder.",
                    "operations": {k: sorted(v) for k, v in GROUPS.items()},
                },
                indent=2,
            )
        )
        return 0
    command = shutil.which("playwriter")
    if not command:
        parser.exit(1, "playwriter not found; use the owning skill's verified npx/bunx fallback and full docs.\n")
    run = subprocess.run([command, "skill"], capture_output=True, check=False)
    if run.returncode:
        sys.stderr.buffer.write(run.stderr)
        return run.returncode
    raw = run.stdout
    # Audited cli.js console.log adds exactly one newline to the source file.
    if raw.endswith(b"\n") and hashlib.sha256(raw[:-1]).hexdigest() == AUDITED_SHA:
        raw = raw[:-1]
    canonical = Path(command).resolve()
    version = None
    for directory in canonical.parents:
        package = directory / "package.json"
        if not package.is_file():
            continue
        try:
            metadata = json.loads(package.read_text())
        except (OSError, ValueError):
            break
        if metadata.get("name") == "playwriter":
            version = metadata.get("version")
        break
    identity = {"command": [str(canonical), "skill"], "version": version}
    content, receipt = select(raw, args.groups or ["core"], version=version)
    print(json.dumps(identity | receipt, sort_keys=True), file=sys.stderr)
    sys.stdout.buffer.write(content)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
