#!/usr/bin/env python3
"""Verify the ``.mermaids/`` navigation map's file-census claims against reality.

The ``.mermaids/`` diagrams are the repo's mandated first-read navigation cloud
(see ``AGENTS.md``). Several of them promise *exhaustive* per-file coverage of a
subtree and state a hard count, e.g. ``Every file under home/exact_bin/ (73)``.
Those counts rot the moment a file is added or removed, yet nothing checked them
-- so an agent that trusts the map gets a false anchor (a C8 evidence-ledger
violation baked into the one artifact every session reads first).

This validator is the ``verify_templates.py`` of the navigation map: for each
declared census claim it (1) confirms the claimed count still appears verbatim
in the diagram prose -- so the table below cannot silently drift from the text
it guards -- and (2) recomputes the real count from git's effective worktree file
set and fails on any divergence, printing ``claimed N, actual M``.

Scope is deliberately the *file-census* claims (the "Every file under X (N)"
contract plus the total effective-file count): they are unambiguous, rot on every
add/remove, and need only ``git`` + stdlib. Structural sub-counts that depend on
toolchain semantics (Go packages via ``go list``, neovim plugin specs, skill
dirs) are intentionally out of scope and are checked by inspection, not here.

Usage:
    verify_mermaids.py [REPO_ROOT]

Exit status is non-zero if any claim's prose anchor is missing or its count has
drifted from the effective worktree file set.
"""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Claim:
    """A single file-census assertion about the navigation map.

    ``globs`` are git pathspecs whose matched-file count must equal ``claimed``;
    ``globs=None`` means the total file count. ``anchors`` are
    ``(filename, substring)`` pairs: each ``substring`` (which embeds ``claimed``)
    must appear verbatim in ``.mermaids/<filename>``, keeping this table and the
    prose it guards in lockstep.
    """

    name: str
    globs: list[str] | None
    claimed: int
    anchors: list[tuple[str, str]] = field(default_factory=list)


# Census claims. When a subtree gains/loses an effective file, update both the
# diagram prose AND the matching ``claimed`` value here (documentation hygiene).
CENSUS: list[Claim] = [
    Claim(
        name="total effective git files",
        globs=None,
        claimed=1272,
        anchors=[
            ("README.md", "1272 files in the effective git file set"),
            ("00-overview.mmd", "1272 files in the effective git file set"),
            ("00-overview.mmd", "file census (1272 total)"),
        ],
    ),
    Claim(
        name="home/.chezmoitemplates/brews/",
        globs=["home/.chezmoitemplates/brews/*"],
        claimed=49,
        anchors=[("02-package-management.mmd", "brews/ (49)")],
    ),
    Claim(
        name="home/.chezmoiscripts/",
        globs=["home/.chezmoiscripts/*"],
        claimed=29,
        anchors=[("01-chezmoi-pipeline.mmd", ".chezmoiscripts/ (29)")],
    ),
    Claim(
        name="home/dot_config/exact_tmux/",
        globs=["home/dot_config/exact_tmux/*"],
        claimed=120,
        anchors=[
            ("05-tmux-pickers.mmd", "exact_tmux/ (120)"),
            ("README.md", "`exact_tmux/` (120)"),
        ],
    ),
    Claim(
        name="home/dot_config/exact_nvim/",
        globs=["home/dot_config/exact_nvim/*"],
        claimed=155,
        anchors=[
            ("07b-neovim.mmd", "exact_nvim/ (155)"),
            ("README.md", "`exact_nvim/` (155)"),
            ("00-overview.mmd", "nvim 155"),
        ],
    ),
    Claim(
        name="home/dot_config/exact_nvim/exact_lua/exact_plugins_local/",
        globs=["home/dot_config/exact_nvim/exact_lua/exact_plugins_local/*"],
        claimed=14,
        anchors=[
            ("07b-neovim.mmd", "exact_plugins_local/ (loaders, 14 each)"),
            ("README.md", "local plugins (14 each)"),
        ],
    ),
    Claim(
        name="home/dot_config/exact_nvim/exact_lua/exact_plugins_local_src/",
        globs=["home/dot_config/exact_nvim/exact_lua/exact_plugins_local_src/*"],
        claimed=14,
        anchors=[
            ("07b-neovim.mmd", "exact_plugins_local_src/ (implementations, 14 each)"),
            ("README.md", "local plugins (14 each)"),
        ],
    ),
    Claim(
        name="home/dot_config/fish/",
        globs=["home/dot_config/fish/*"],
        claimed=77,
        anchors=[("00-overview.mmd", "fish 77")],
    ),
    Claim(
        name="home/exact_bin/",
        globs=["home/exact_bin/*"],
        claimed=74,
        anchors=[
            ("07c-bin-commands.mmd", "exact_bin/ (74 thin commands)"),
            ("README.md", "`exact_bin/` (74)"),
        ],
    ),
    Claim(
        name="home/exact_lib/",
        globs=["home/exact_lib/*"],
        claimed=65,
        anchors=[
            ("07c-bin-commands.mmd", "home/exact_lib/ (65 command/shared library files)"),
            ("README.md", "`home/exact_lib/` (65 command/shared library files)"),
        ],
    ),
    Claim(
        name="home/exact_dot_agents/",
        globs=["home/exact_dot_agents/*"],
        claimed=106,
        anchors=[
            ("03b-agent-skills-hooks.mmd", "exact_dot_agents/ (106)"),
            ("00-overview.mmd", "agents 106"),
        ],
    ),
    Claim(
        name="scripts/",
        globs=["scripts/*"],
        claimed=92,
        anchors=[
            ("11-scripts-helpers.mmd", "scripts/ (92)"),
            ("README.md", "`scripts/` (92)"),
            ("00-overview.mmd", "scripts 92"),
        ],
    ),
    Claim(
        name="home/exact_lib/exact_,palantir/",
        globs=["home/exact_lib/exact_,palantir/*"],
        claimed=12,
        anchors=[("04-palantir-state-machine.mmd", "home/exact_lib/exact_,palantir/ (12)")],
    ),
]


def _git_ls_files(repo_root: Path, globs: list[str] | None) -> int:
    """Count the effective git worktree file set, all or matching ``globs``.

    Include tracked files that still exist plus untracked, non-ignored files.
    That makes local add/remove checks work before staging, while ignored scratch
    files still stay out of the census.
    """
    cmd = ["git", "-C", str(repo_root), "ls-files", "--cached", "--others", "--exclude-standard"]
    if globs is not None:
        cmd += ["--", *globs]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    seen: set[str] = set()
    for line in result.stdout.splitlines():
        rel = line.strip()
        if not rel or rel in seen:
            continue
        path = repo_root / rel
        if path.exists() or path.is_symlink():
            seen.add(rel)
    return len(seen)


def check_claims(repo_root: Path, claims: list[Claim] | None = None) -> list[str]:
    """Return a list of human-readable failure messages (empty when all pass)."""
    claims = CENSUS if claims is None else claims
    mermaids_dir = repo_root / ".mermaids"
    failures: list[str] = []

    for claim in claims:
        actual = _git_ls_files(repo_root, claim.globs)
        if actual != claim.claimed:
            failures.append(f"{claim.name}: claimed {claim.claimed}, actual {actual} (effective git files)")

        for filename, substring in claim.anchors:
            path = mermaids_dir / filename
            if not path.is_file():
                failures.append(f"{claim.name}: anchor file missing: .mermaids/{filename}")
                continue
            if substring not in path.read_text(encoding="utf-8"):
                failures.append(f'{claim.name}: anchor not found in .mermaids/{filename}: "{substring}"')

    return failures


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) > 1:
        print("Usage: verify_mermaids.py [REPO_ROOT]", file=sys.stderr)
        return 2

    if args:
        repo_root = Path(args[0]).expanduser().resolve()
    else:
        repo_root = Path(__file__).resolve().parent.parent

    if not (repo_root / ".mermaids").is_dir():
        print(f".mermaids/ not found under {repo_root}", file=sys.stderr)
        return 2

    failures = check_claims(repo_root)
    if failures:
        print(f"mermaids census verification failed ({len(failures)} issue(s)):", file=sys.stderr)
        for message in failures:
            print(f"  \u2717 {message}", file=sys.stderr)
        return 1

    print(f"mermaids census verification passed ({len(CENSUS)} claims)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
