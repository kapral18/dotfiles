"""Facts about the current Kibana checkout: git worktree, branch, package manager, ES version.

Kibana always runs from the worktree source (``pnpm start``, or ``yarn start`` on
a branch without ``pnpm-lock.yaml``); there is no prebuilt image for an
arbitrary branch.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from kbn_stack import config


def git_output(args: list[str]) -> str:
    result = subprocess.run(["git", *args], capture_output=True, text=True, check=False)
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def package_manager(worktree: str) -> str:
    """Kibana's package manager for this checkout: pnpm once the branch carries
    ``pnpm-lock.yaml`` (elastic/kibana main since the yarn -> pnpm migration,
    which keeps ``yarn.lock`` around, so only the pnpm lockfile discriminates),
    yarn on older branches.
    """
    return "pnpm" if (Path(worktree) / "pnpm-lock.yaml").is_file() else "yarn"


def resolve_worktree() -> str:
    top = git_output(["rev-parse", "--show-toplevel"])
    if not top:
        config.fail("not inside a git worktree (run from a Kibana checkout)")
    return str(Path(top).resolve())


def current_branch() -> str:
    branch = git_output(["rev-parse", "--abbrev-ref", "HEAD"])
    return branch or "detached"


def sanitize(name: str) -> str:
    """Make a branch name safe for a directory / cookie suffix."""
    return re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip("-") or "stack"


def changed_paths(worktree: str) -> list[str]:
    """Paths the branch changed since its merge base with main, including uncommitted and untracked files."""
    base = ""
    for ref in ("origin/main", "main"):
        base = git_output(["-C", worktree, "merge-base", "HEAD", ref])
        if base:
            break
    if not base:
        print(
            ",kbn-stack: no origin/main or main to diff against; skipping the saved-object isolation check.",
            flush=True,
        )
        return []
    tracked = git_output(["-C", worktree, "diff", "--name-only", base]).splitlines()
    # A brand-new saved-object type file exists before `git add`; `git diff` never lists it.
    untracked = git_output(["-C", worktree, "ls-files", "--others", "--exclude-standard"]).splitlines()
    return [line for line in [*tracked, *untracked] if line]


def isolation_signal_paths(paths: list[str]) -> list[str]:
    """The subset of ``paths`` whose change would mutate a shared ES from under other worktrees.

    Only server-side, non-test files count: saved-object type definitions,
    model versions and migrations, index templates, and ingest pipelines
    (``config.ISOLATION_PATH_MARKERS``). Server-side means a plugin ``server/``
    tree or a core ``*server-internal`` package (``src/core/packages/saved-objects/*-server-internal``).
    """
    hits: list[str] = []
    for path in paths:
        name = path.rsplit("/", 1)[-1]
        if ".test." in name or "/__snapshots__/" in path or "/__mocks__/" in path or "/__fixtures__/" in path:
            continue
        if "server/" not in path and "server-internal/" not in path:
            continue
        if any(marker in path for marker in config.ISOLATION_PATH_MARKERS):
            hits.append(path)
    return hits


def isolation_signals(worktree: str) -> list[str]:
    """Changed paths that make this branch unsafe to attach to a shared ES."""
    return isolation_signal_paths(changed_paths(worktree))


def read_worktree_version(worktree: str) -> str | None:
    """The worktree's package.json version -- the ES version `<pm> es snapshot` downloads.

    Kibana's scripts/es.js passes ``version: pkg.version`` to kbn-es, so two
    worktrees resolve to the same ES artifact exactly when this field matches.
    """
    try:
        version = json.loads((Path(worktree) / "package.json").read_text(encoding="utf-8")).get("version")
    except (OSError, json.JSONDecodeError, AttributeError):
        return None
    return version if isinstance(version, str) and version else None
