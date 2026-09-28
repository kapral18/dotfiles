"""State root, workspace, repo identity, and catalog layout.

Mirrors the ``,proof`` state-root / workspace-guard pattern
(``home/exact_lib/exact_,proof/main.py``): the catalog root resolves from
``AGENT_FORMAL_HOME`` > ``XDG_STATE_HOME/agent-formal`` > ``~/.local/state/agent-formal``
and refuses to live inside the current git workspace. Unlike ``,proof`` (keyed
per git toplevel), the repo id here is keyed by the shared git common-dir so
worktrees of the same repo see the same catalog.
"""

from __future__ import annotations

import os
from pathlib import Path

from .util import CliError, run, sha256_hex, short_hash

APP = "agent-formal"
PINNED_TOOLCHAIN = "leanprover/lean4:v4.34.1"


def lib_dir() -> Path:
    """Root of the deployed ,formal command library (``~/lib/,formal``)."""
    explicit = os.environ.get("FORMAL_LIB_DIR")
    if explicit:
        return Path(explicit).expanduser().resolve()
    return Path(__file__).resolve().parent.parent


def state_root() -> Path:
    """Resolve the catalog state root. ``AGENT_FORMAL_HOME``/``XDG_STATE_HOME`` are always
    resolved to an absolute path (``Path(...).expanduser().resolve()``, matching ``lib_dir``'s
    own ``FORMAL_LIB_DIR`` handling): a relative value would otherwise be baked verbatim into a
    later-written ``KIT_PATH`` (see ``manifest.init_unit``), which ``lake build`` resolves
    against the *unit dir* it runs in (``build.lake_build``'s ``cwd=unit_dir``) rather than
    whatever directory the caller happened to be in when the relative value was first read."""
    explicit = os.environ.get("AGENT_FORMAL_HOME")
    if explicit:
        return Path(explicit).expanduser().resolve()
    xdg_state = os.environ.get("XDG_STATE_HOME")
    if xdg_state:
        return (Path(xdg_state).expanduser() / APP).resolve()
    return Path.home() / ".local" / "state" / APP


def _git_text(argv: list[str], cwd: Path) -> str | None:
    result = run(["git", *argv], cwd=cwd, timeout=10)
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def workspace_root(workspace_arg: str | None = None) -> Path:
    start = Path(workspace_arg).expanduser() if workspace_arg else Path.cwd()
    start = start.resolve()
    top = _git_text(["rev-parse", "--show-toplevel"], start)
    return Path(top).resolve() if top else start


def guard_state_root_outside_workspace(root: Path, workspace: Path) -> None:
    root_resolved = root.resolve()
    workspace_resolved = workspace.resolve()
    # Mirrors ,proof's own exception (home/exact_lib/exact_,proof/main.py:119): when no git repo
    # is found, workspace resolution falls back to cwd, which can equal $HOME -- and the state
    # root always nests under $HOME, so the naive check would then always refuse. Only a real
    # (non-$HOME) workspace triggers the guard.
    if workspace_resolved == Path.home().resolve():
        return
    try:
        inside = root_resolved.is_relative_to(workspace_resolved)
    except AttributeError:  # pragma: no cover - py<3.9 fallback, unused here
        inside = str(root_resolved).startswith(str(workspace_resolved) + os.sep)
    if inside:
        raise CliError(
            "Formal catalog state must stay outside the git workspace. "
            "Set AGENT_FORMAL_HOME or XDG_STATE_HOME to a repo-external directory.",
            code=2,
        )


def git_common_dir(workspace: Path) -> Path:
    out = _git_text(["rev-parse", "--git-common-dir"], workspace)
    if not out:
        raise CliError(f"Not a git repository: {workspace}", code=2)
    common = Path(out)
    if not common.is_absolute():
        common = workspace / common
    return common.resolve()


def repo_id(workspace: Path) -> str:
    common = git_common_dir(workspace)
    return short_hash(str(common).encode("utf-8"))


def remote_url(workspace: Path) -> str | None:
    return _git_text(["remote", "get-url", "origin"], workspace)


def head_commit(workspace: Path) -> str | None:
    return _git_text(["rev-parse", "HEAD"], workspace)


def current_branch(workspace: Path) -> str | None:
    return _git_text(["symbolic-ref", "--short", "-q", "HEAD"], workspace)


def branch_slug(workspace: Path) -> str:
    """Collision-resistant storage key for the current full branch ref or detached commit."""
    branch = current_branch(workspace)
    if branch:
        ref = f"refs/heads/{branch}"
        return f"branch-{sha256_hex(ref.encode('utf-8'))}"
    commit = _git_text(["rev-parse", "HEAD"], workspace) or "unknown"
    return f"detached-{sha256_hex(commit.encode('utf-8'))}"


class Layout:
    """Resolved catalog paths for one repo (shared across its worktrees)."""

    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace
        self.root = state_root()
        guard_state_root_outside_workspace(self.root, workspace)
        self.repo_id = repo_id(workspace)
        self.repo_dir = self.root / self.repo_id
        self._guard_catalog_path(self.repo_dir, "repository")

    @staticmethod
    def _identifier(value: str, kind: str) -> str:
        if (
            not value
            or "\0" in value
            or value in {".", ".."}
            or Path(value).is_absolute()
            or "/" in value
            or "\\" in value
        ):
            raise CliError(f"Invalid {kind} identifier: {value!r}", code=2)
        return value

    def _guard_catalog_path(self, candidate: Path, kind: str) -> Path:
        """Keep every selected catalog path under the trusted state root and outside the workspace."""
        try:
            candidate.resolve().relative_to(self.root.resolve())
        except (OSError, RuntimeError, ValueError) as exc:
            raise CliError(f"{kind.capitalize()} path escapes the formal catalog: {candidate}", code=2) from exc
        guard_state_root_outside_workspace(candidate, self.workspace)
        return candidate

    def _contained_path(self, base: Path, identifier: str, kind: str) -> Path:
        identifier = self._identifier(identifier, kind)
        candidate = self._guard_catalog_path(base / identifier, kind)
        try:
            candidate.resolve().relative_to(base.absolute())
        except (OSError, RuntimeError, ValueError) as exc:
            raise CliError(f"{kind.capitalize()} path escapes its catalog subtree: {candidate}", code=2) from exc
        return candidate

    def kit_dir(self, kit_hash: str) -> Path:
        return self.root / "_kit" / kit_hash

    def repo_json(self) -> Path:
        return self.repo_dir / "repo.json"

    def index_json(self) -> Path:
        return self.repo_dir / "index.json"

    def work_dir(self, unit: str, branch: str | None = None) -> Path:
        slug = branch or branch_slug(self.workspace)
        branch_dir = self._contained_path(self.repo_dir / "work", slug, "branch")
        return self._contained_path(branch_dir, unit, "unit")

    def unit_versions_dir(self, unit: str) -> Path:
        unit_dir = self._contained_path(self.repo_dir / "units", unit, "unit")
        return self._guard_catalog_path(unit_dir / "versions", "unit")

    def version_dir(self, unit: str, version_id: str) -> Path:
        return self._contained_path(self.unit_versions_dir(unit), version_id, "version")

    def exports_dir(self) -> Path:
        """Temporary plain exports of a ref (throwaway-index ``git checkout-index``) for differential replay
        (see ``replay._export_ref``); never a ``git worktree``."""
        return self.root / "_exports"
