#!/usr/bin/env python3
"""Verify comma commands have Fish completions and no orphaned command libraries.

Usage: verify_bin_surface.py [REPO_ROOT]
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CommandSurface:
    """A comma command and its required Fish completion."""

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


def _command_references_library(command: CommandSurface, library_name: str) -> bool:
    try:
        source = command.source.read_text(encoding="utf-8")
    except OSError:
        return False
    return f"lib/,{library_name}/" in source


def check_bin_surface(repo_root: Path) -> list[str]:
    """Return human-readable failures for command-surface drift."""

    failures: list[str] = []

    commands = discover_commands(repo_root)
    command_names = {command.name for command in commands}

    for command in commands:
        display = _command_token(command.name)
        if not command.fish_completion.is_file():
            failures.append(f"{display}: missing Fish completion {command.fish_completion.relative_to(repo_root)}")

    for library in discover_command_libraries(repo_root):
        if library.name not in command_names and not any(
            _command_references_library(command, library.name) for command in commands
        ):
            failures.append(
                f",{library.name}: command library {library.source.relative_to(repo_root)} "
                "has no matching command or explicit launcher reference"
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
