#!/usr/bin/env python3
"""Verify the ``.mermaids/`` navigation map's file-census claims against reality.

The ``.mermaids/`` diagrams are the repo's mandated first-read navigation cloud
(see ``AGENTS.md``). Several of them promise *exhaustive* per-file coverage of a
subtree and state a hard count, e.g. ``Every file under home/exact_bin/ (77)``.
Those counts rot the moment a file is added or removed, yet nothing checked them
-- so an agent that trusts the map gets a false anchor (a C8 evidence-ledger
violation baked into the one artifact every session reads first).

This validator is the ``verify_templates.py`` of the navigation map: for each
declared census claim it (1) confirms the claimed count still appears verbatim
in the diagram prose -- so the table below cannot silently drift from the text
it guards -- and (2) recomputes the real count from ``git ls-files`` and fails on
any divergence, printing ``claimed N, actual M``.

Scope is deliberately the *file-census* claims (the "Every file under X (N)"
contract plus the total tracked-file count): they are unambiguous, rot on every
add/remove, and need only ``git`` + stdlib. Structural sub-counts that depend on
toolchain semantics (Go packages via ``go list``, neovim plugin specs, skill
dirs) are intentionally out of scope and are checked by inspection, not here.

Usage:
    verify_mermaids.py [REPO_ROOT]

Exit status is non-zero if any claim's prose anchor is missing or its count has
drifted from ``git ls-files``.
"""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Claim:
    """A single file-census assertion about the navigation map.

    ``globs`` are ``git ls-files`` pathspecs whose matched-file count must equal
    ``claimed``; ``globs=None`` means the total tracked-file count. ``anchors``
    are ``(diagram_filename, substring)`` pairs: each ``substring`` (which
    embeds ``claimed``) must appear verbatim in ``.mermaids/<diagram_filename>``,
    keeping this table and the diagram prose in lockstep.
    """

    name: str
    globs: list[str] | None
    claimed: int
    anchors: list[tuple[str, str]] = field(default_factory=list)


# Census claims. When a subtree gains/loses a tracked file, update both the
# diagram prose AND the matching ``claimed`` value here (documentation hygiene).
CENSUS: list[Claim] = [
    Claim(
        name="total tracked files",
        globs=None,
        claimed=967,
        anchors=[("README.md", "967 tracked files")],
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
        claimed=30,
        anchors=[("01-chezmoi-pipeline.mmd", ".chezmoiscripts/ (30)")],
    ),
    Claim(
        name="home/dot_config/exact_tmux/",
        globs=["home/dot_config/exact_tmux/*"],
        claimed=117,
        anchors=[
            ("05-tmux-pickers.mmd", "exact_tmux/ (117)"),
            ("README.md", "`exact_tmux/` (117)"),
        ],
    ),
    Claim(
        name="home/dot_config/exact_nvim/",
        globs=["home/dot_config/exact_nvim/*"],
        claimed=157,
        anchors=[
            ("07b-neovim.mmd", "exact_nvim/ (157)"),
            ("README.md", "`exact_nvim/` (157)"),
        ],
    ),
    Claim(
        name="home/exact_bin/",
        globs=["home/exact_bin/*"],
        claimed=80,
        anchors=[
            ("07c-bin-commands.mmd", "exact_bin/ (80 incl. utils)"),
            ("README.md", "`exact_bin/` (80)"),
        ],
    ),
    Claim(
        name="home/exact_dot_agents/",
        globs=["home/exact_dot_agents/*"],
        claimed=58,
        anchors=[("03b-agent-skills-hooks.mmd", "exact_dot_agents/ (58)")],
    ),
    Claim(
        name="scripts/",
        globs=["scripts/*"],
        claimed=42,
        anchors=[
            ("11-scripts-helpers.mmd", "scripts/ (42)"),
            ("README.md", "`scripts/` (42)"),
        ],
    ),
]


def _git_ls_files(repo_root: Path, globs: list[str] | None) -> int:
    """Count tracked files via ``git ls-files`` (all, or matching ``globs``)."""
    cmd = ["git", "-C", str(repo_root), "ls-files"]
    if globs is not None:
        cmd += ["--", *globs]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return sum(1 for line in result.stdout.splitlines() if line.strip())


def check_claims(repo_root: Path, claims: list[Claim] | None = None) -> list[str]:
    """Return a list of human-readable failure messages (empty when all pass)."""
    claims = CENSUS if claims is None else claims
    mermaids_dir = repo_root / ".mermaids"
    failures: list[str] = []

    for claim in claims:
        actual = _git_ls_files(repo_root, claim.globs)
        if actual != claim.claimed:
            failures.append(f"{claim.name}: claimed {claim.claimed}, actual {actual} (git ls-files)")

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
