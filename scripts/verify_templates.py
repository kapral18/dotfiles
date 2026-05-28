#!/usr/bin/env python3
"""Verify every chezmoi template under the source tree renders cleanly.

Each managed ``*.tmpl`` file is piped through ``chezmoi execute-template`` so
that parse errors, unbalanced actions, undefined data keys, and renamed
``.chezmoidata`` fields are caught here -- before they break ``chezmoi apply``
on a real machine (the worst time to discover them is a fresh bootstrap).

Usage:
    verify_templates.py [SOURCE_DIR]

SOURCE_DIR defaults to the repo's ``home/`` directory (the chezmoi source root).
``chezmoi``'s own config template (``.chezmoi.toml.tmpl``) is skipped: it uses
interactive ``prompt*`` functions that only exist during ``chezmoi init``, not
``execute-template``.

Exit status is non-zero if any template fails to render.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def find_templates(source_dir: Path) -> list[Path]:
    """Return sorted ``*.tmpl`` files under ``source_dir``.

    chezmoi's special config/data templates (basenames starting with
    ``.chezmoi``) are excluded: they are rendered by ``chezmoi init`` with a
    different function set (interactive ``prompt*``), not by ``execute-template``.
    """
    return sorted(p for p in source_dir.rglob("*.tmpl") if p.is_file() and not p.name.startswith(".chezmoi"))


def render_template(path: Path) -> tuple[bool, str]:
    """Render one template via ``chezmoi execute-template``.

    Returns ``(ok, message)``; ``message`` carries chezmoi's stderr on failure.
    """
    try:
        result = subprocess.run(
            ["chezmoi", "execute-template"],
            input=path.read_bytes(),
            capture_output=True,
            check=False,
        )
    except OSError as exc:
        return False, f"failed to run chezmoi execute-template: {exc}"
    if result.returncode == 0:
        return True, ""
    return False, result.stderr.decode("utf-8", "replace").strip()


def _display_path(path: Path, source_dir: Path) -> str:
    try:
        return str(path.relative_to(source_dir.parent))
    except ValueError:
        return str(path)


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) > 1:
        print("Usage: verify_templates.py [SOURCE_DIR]", file=sys.stderr)
        return 2

    if args:
        source_dir = Path(args[0]).expanduser()
    else:
        source_dir = Path(__file__).resolve().parent.parent / "home"

    if not source_dir.is_dir():
        print(f"source dir not found: {source_dir}", file=sys.stderr)
        return 2

    templates = find_templates(source_dir)
    if not templates:
        print(f"no templates found under {source_dir}")
        return 0

    failures: list[tuple[Path, str]] = []
    for path in templates:
        ok, message = render_template(path)
        if not ok:
            failures.append((path, message))

    if failures:
        print(
            f"template verification failed ({len(failures)}/{len(templates)} did not render):",
            file=sys.stderr,
        )
        for path, message in failures:
            print(f"  \u2717 {_display_path(path, source_dir)}", file=sys.stderr)
            for line in message.splitlines():
                print(f"      {line}", file=sys.stderr)
        return 1

    print(f"template verification passed ({len(templates)} templates rendered)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
