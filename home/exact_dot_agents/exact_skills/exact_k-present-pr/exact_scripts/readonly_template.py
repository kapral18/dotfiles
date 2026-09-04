#!/usr/bin/env python3
"""Prepare editable presentation HTML and restore the template's fixed CSS/JS.

Usage: python3 template.py prepare TEMPLATE DRAFT
       python3 template.py render TEMPLATE DRAFT OUTPUT
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

MARKERS = {
    b"style": b"<!-- K_PRESENT_PR_FIXED_STYLE -->",
    b"script": b"<!-- K_PRESENT_PR_FIXED_SCRIPT -->",
}


def split_template(template: bytes) -> tuple[bytes, dict[bytes, bytes]]:
    """Replace each canonical fixed block with its reserved editing marker."""
    blocks = {}
    editable = template
    for tag, marker in MARKERS.items():
        if marker in template:
            raise ValueError("template already contains a reserved editing marker")
        pattern = rb"<" + tag + rb"\b[^>]*>.*?</" + tag + rb"\s*>"
        matches = list(re.finditer(pattern, editable, flags=re.DOTALL | re.IGNORECASE))
        if len(matches) != 1:
            raise ValueError(f"template must contain exactly one {tag.decode()} block")
        match = matches[0]
        blocks[marker] = match.group()
        editable = editable[: match.start()] + marker + editable[match.end() :]
    return editable, blocks


def render(template: bytes, draft: bytes) -> bytes:
    """Restore fixed blocks without parsing or rewriting the editable markup."""
    _, blocks = split_template(template)
    for marker in blocks:
        if draft.count(marker) != 1:
            raise ValueError(f"draft must contain exactly one {marker.decode()}")
    remainder = draft
    for marker in blocks:
        remainder = remainder.replace(marker, b"")
    if re.search(rb"<!--\s*K_PRESENT_PR_FIXED_", remainder):
        raise ValueError("draft contains an unknown or damaged editing marker")
    result = draft
    for marker, block in blocks.items():
        result = result.replace(marker, block)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("prepare", "render"):
        command = commands.add_parser(name)
        command.add_argument("template", type=Path)
        command.add_argument("draft", type=Path)
        if name == "render":
            command.add_argument("output", type=Path)
    args = parser.parse_args()
    destination = args.draft if args.command == "prepare" else args.output
    inputs = [args.template] + ([args.draft] if args.command == "render" else [])
    if any(
        destination.resolve() == source.resolve()
        or (destination.exists() and source.exists() and destination.samefile(source))
        for source in inputs
    ):
        parser.error("output must be separate from its inputs")
    try:
        template = args.template.read_bytes()
        if args.command == "prepare":
            content, _ = split_template(template)
        else:
            content = render(template, args.draft.read_bytes())
        destination.write_bytes(content)
    except (OSError, ValueError) as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
