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

import re
import subprocess
import sys
from pathlib import Path

SINGLE_INCLUDE_RE = re.compile(r'\s*\{\{-?\s*include\s+"([^"]+)"\s*-?\}\}\s*\Z')


def find_templates(source_dir: Path) -> list[Path]:
    """Return sorted ``*.tmpl`` files under ``source_dir``.

    chezmoi's special config/data templates (basenames starting with
    ``.chezmoi``) are excluded: they are rendered by ``chezmoi init`` with a
    different function set (interactive ``prompt*``), not by ``execute-template``.
    """
    return sorted(p for p in source_dir.rglob("*.tmpl") if p.is_file() and not p.name.startswith(".chezmoi"))


def exact_projection_error(path: Path, source_dir: Path, rendered: bytes) -> str | None:
    """Return an error when an exact-lib single include changes source bytes."""
    try:
        path.relative_to(source_dir / "exact_lib")
    except ValueError:
        return None
    match = SINGLE_INCLUDE_RE.fullmatch(path.read_text(encoding="utf-8"))
    if match is None:
        return None
    included = (source_dir / match.group(1)).resolve()
    repo_root = source_dir.resolve().parent
    if not included.is_relative_to(repo_root) or not included.is_file():
        return f"single-include projection source is unavailable: {included}"
    if rendered != included.read_bytes():
        return f"single-include projection must render byte-identically to {included.relative_to(repo_root)}"
    return None


def chezmoi_source_root(source_dir: Path) -> Path:
    """Resolve a chezmoi source root without widening standalone fixture scope."""
    source_dir = source_dir.resolve()
    parent = source_dir.parent
    marker = parent / ".chezmoiroot"
    try:
        configured_root = marker.read_text(encoding="utf-8").strip()
    except OSError:
        return source_dir
    if configured_root and (parent / configured_root).resolve() == source_dir:
        return parent
    return source_dir


def render_template(path: Path, source_dir: Path | None = None) -> tuple[bool, str]:
    """Render one template via ``chezmoi execute-template``.

    Returns ``(ok, message)``; ``message`` carries chezmoi's stderr on failure.
    """
    command = ["chezmoi"]
    if source_dir is not None:
        command += ["--source", str(chezmoi_source_root(source_dir))]
    command.append("execute-template")
    try:
        result = subprocess.run(
            command,
            input=path.read_bytes(),
            capture_output=True,
            check=False,
        )
    except OSError as exc:
        return False, f"failed to run chezmoi execute-template: {exc}"
    if result.returncode == 0:
        if source_dir is not None:
            message = exact_projection_error(path, source_dir, result.stdout)
            if message is not None:
                return False, message
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
        ok, message = render_template(path, source_dir)
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
