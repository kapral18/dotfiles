#!/usr/bin/env python3
"""Verify comma command discoverability stays in sync.

User-facing commands live in ``home/exact_bin/executable_,<name>`` and are
deployed to ``~/bin/,<name>``. AGENTS.md requires each command to carry a Fish
completion plus docs/catalog coverage, but that contract used to be reviewed by
hand. This check turns the command surface into a machine-verifiable gate.

Usage:
    verify_bin_surface.py [REPO_ROOT]

Exit status is non-zero if any command is missing:

- ``home/dot_config/fish/completions/readonly_,<name>.fish``
- a backticked command token under ``docs/topics/workflow/custom-commands/``
- a command token in ``.mermaids/07c-bin-commands.mmd``
- no orphaned command-library directory under ``home/exact_lib/exact_,<name>/``
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

COMMAND_TOKEN_CHARS = r"A-Za-z0-9-"


@dataclass(frozen=True)
class CommandSurface:
    """The files that must exist/mention one comma command."""

    name: str
    source: Path
    fish_completion: Path


@dataclass(frozen=True)
class CommandLibrary:
    """A deployed internal library directory for one comma command."""

    name: str
    source: Path


def _command_name(path: Path) -> str:
    name = path.name.removeprefix("executable_,")
    if name.endswith(".tmpl"):
        name = name.removesuffix(".tmpl")
    return name


def _command_token(name: str) -> str:
    return f",{name}"


def _command_token_regex(name: str) -> re.Pattern[str]:
    token = re.escape(_command_token(name))
    return re.compile(rf"(?<![{COMMAND_TOKEN_CHARS}]){token}(?![{COMMAND_TOKEN_CHARS}])")


def discover_commands(repo_root: Path) -> list[CommandSurface]:
    """Return comma commands declared directly under ``home/exact_bin``."""

    bin_dir = repo_root / "home" / "exact_bin"
    completion_dir = repo_root / "home" / "dot_config" / "fish" / "completions"
    commands: list[CommandSurface] = []
    for source in sorted(bin_dir.glob("executable_,*")):
        if not source.is_file():
            continue
        name = _command_name(source)
        commands.append(
            CommandSurface(
                name=name,
                source=source,
                fish_completion=completion_dir / f"readonly_,{name}.fish",
            )
        )
    return commands


def discover_command_libraries(repo_root: Path) -> list[CommandLibrary]:
    """Return deployed command internals declared under ``home/exact_lib/exact_,<name>``."""

    lib_dir = repo_root / "home" / "exact_lib"
    libraries: list[CommandLibrary] = []
    for source in sorted(lib_dir.iterdir() if lib_dir.is_dir() else []):
        if not source.is_dir():
            continue
        source_name = source.name
        if source_name.startswith("exact_"):
            source_name = source_name.removeprefix("exact_")
        if not source_name.startswith(","):
            continue
        libraries.append(CommandLibrary(name=source_name.removeprefix(","), source=source))
    return libraries


def _read_required(path: Path) -> str:
    if not path.is_file():
        raise FileNotFoundError(path)
    return path.read_text(encoding="utf-8")


def _read_docs_dir(path: Path) -> str:
    if not path.is_dir():
        raise FileNotFoundError(path)
    docs_files = sorted(path.glob("*.md"))
    if not docs_files:
        raise FileNotFoundError(path / "*.md")
    return "\n".join(p.read_text(encoding="utf-8") for p in docs_files)


def _docs_mentions_command(docs_text: str, name: str) -> bool:
    return re.search(rf"`{re.escape(_command_token(name))}`", docs_text) is not None


def _mermaid_mentions_command(mermaid_text: str, name: str) -> bool:
    return _command_token_regex(name).search(mermaid_text) is not None


def check_bin_surface(repo_root: Path) -> list[str]:
    """Return human-readable failures for command-surface drift."""

    docs_path = repo_root / "docs" / "topics" / "workflow" / "custom-commands"
    mermaid_path = repo_root / ".mermaids" / "07c-bin-commands.mmd"
    failures: list[str] = []

    try:
        docs_text = _read_docs_dir(docs_path)
        docs_available = True
    except FileNotFoundError:
        failures.append(f"docs file missing: {docs_path.relative_to(repo_root)}")
        docs_text = ""
        docs_available = False

    try:
        mermaid_text = _read_required(mermaid_path)
    except FileNotFoundError:
        failures.append(f"mermaid catalog missing: {mermaid_path.relative_to(repo_root)}")
        mermaid_text = ""

    commands = discover_commands(repo_root)
    command_names = {command.name for command in commands}

    for command in commands:
        display = _command_token(command.name)
        if not command.fish_completion.is_file():
            failures.append(f"{display}: missing Fish completion {command.fish_completion.relative_to(repo_root)}")
        if docs_available and not _docs_mentions_command(docs_text, command.name):
            failures.append(f"{display}: missing docs token in {docs_path.relative_to(repo_root)}/")
        if mermaid_text and not _mermaid_mentions_command(mermaid_text, command.name):
            failures.append(f"{display}: missing catalog token in {mermaid_path.relative_to(repo_root)}")

    for library in discover_command_libraries(repo_root):
        if library.name not in command_names:
            failures.append(
                f",{library.name}: command library {library.source.relative_to(repo_root)} "
                f"has no matching home/exact_bin/executable_,{library.name}"
            )

    return failures


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) > 1:
        print("Usage: verify_bin_surface.py [REPO_ROOT]", file=sys.stderr)
        return 2

    repo_root = Path(args[0]).expanduser().resolve() if args else Path(__file__).resolve().parent.parent
    if not (repo_root / "home" / "exact_bin").is_dir():
        print(f"home/exact_bin not found under {repo_root}", file=sys.stderr)
        return 2

    failures = check_bin_surface(repo_root)
    if failures:
        print(f"bin surface verification failed ({len(failures)} issue(s)):", file=sys.stderr)
        for failure in failures:
            print(f"  \u2717 {failure}", file=sys.stderr)
        return 1

    print(
        f"bin surface verification passed "
        f"({len(discover_commands(repo_root))} commands, {len(discover_command_libraries(repo_root))} libraries)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
