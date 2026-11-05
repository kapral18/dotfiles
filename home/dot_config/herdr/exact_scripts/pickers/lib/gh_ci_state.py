"""Reduce a GitHub statusCheckRollup to one CI badge state for the pickers."""

from __future__ import annotations

import re
from typing import Any

_TRIVIAL_STATUS_RE = re.compile(
    r"^(CLA|prbot:|renovate/|license/|security/|buildkite/docs)",
    re.IGNORECASE,
)
_TRIVIAL_CHECK_RE = re.compile(
    r"^(Analyze new dependencies|docs-preview)",
    re.IGNORECASE,
)


def is_trivial_ctx(ctx: dict[str, Any]) -> bool:
    """True if a rollup context is a non-CI/bot check we ignore for badge state.

    Trivial contexts (CLA, prbot:*, renovate, license, docs previews, etc.) can
    fail without the PR's real CI being red. They must be excluded both from the
    aggregate fallback AND from the early "rollup is failing" short-circuit;
    otherwise a single failing trivial check (e.g. `prbot:outdated`) masks a
    green canonical CI context and the picker shows a false failure badge.
    """
    typename = ctx.get("__typename", "")
    name = ctx.get("context", "") or ctx.get("name", "")
    if typename == "StatusContext" and _TRIVIAL_STATUS_RE.search(name):
        return True
    if typename == "CheckRun" and _TRIVIAL_CHECK_RE.search(name):
        return True
    return False


def ctx_is_failing(ctx: dict[str, Any]) -> bool:
    if ctx.get("__typename") == "StatusContext":
        return (ctx.get("state") or "").upper() in ("FAILURE", "ERROR")
    if ctx.get("__typename") == "CheckRun":
        return (ctx.get("conclusion") or "").upper() in ("FAILURE", "TIMED_OUT", "CANCELLED")
    return False


def extract_ci_state(commit_node: dict[str, Any], repo_name: str) -> str:
    """Extract meaningful CI state from status check contexts.

    Priority:
    1. StatusContext named '{repo_name}-ci' (e.g. 'kibana-ci')
    2. Buildkite StatusContext for the repo (excluding docs)
    3. CheckRun whose name contains the repo name (excluding docs)
    4. Aggregate state of non-trivial checks (excludes bots/CLA/docs/snyk)
    5. Empty string if only trivial contexts exist (no real CI ran)
    """
    try:
        rollup = commit_node["statusCheckRollup"]
    except (KeyError, TypeError):
        return ""
    if rollup is None:
        return ""

    contexts = []
    try:
        contexts = (rollup.get("contexts") or {}).get("nodes") or []
    except (AttributeError, TypeError):
        pass

    overall_state = (rollup.get("state") or "").upper()
    if not contexts:
        # No per-context detail to reason about; trust the aggregate, but don't
        # invent a failure from a state we can't attribute to a real check.
        return overall_state if overall_state != "ERROR" else "FAILURE"

    # Never show green when a *real* (non-trivial) check is failing. This still
    # prevents a single canonical success context (e.g. kibana-ci) from masking
    # other failing required checks, but a failing trivial context (CLA,
    # prbot:*, renovate, docs preview) no longer fabricates a red badge.
    if overall_state in ("FAILURE", "ERROR") and any(
        ctx_is_failing(ctx) and not is_trivial_ctx(ctx) for ctx in contexts
    ):
        return "FAILURE"

    canonical = f"{repo_name}-ci"
    for ctx in contexts:
        if ctx.get("__typename") == "StatusContext" and ctx.get("context") == canonical:
            return ctx.get("state", "")

    for ctx in contexts:
        if ctx.get("__typename") != "StatusContext":
            continue
        name = ctx.get("context", "")
        if name.startswith("buildkite/") and repo_name in name and "docs" not in name:
            return ctx.get("state", "")

    for ctx in contexts:
        if ctx.get("__typename") != "CheckRun":
            continue
        name = ctx.get("name", "")
        if repo_name in name.lower() and "docs" not in name.lower():
            conclusion = ctx.get("conclusion", "")
            status = ctx.get("status", "")
            if conclusion == "SUCCESS":
                return "SUCCESS"
            if conclusion in ("FAILURE", "TIMED_OUT", "CANCELLED"):
                return "FAILURE"
            if status in ("IN_PROGRESS", "QUEUED", "WAITING"):
                return "PENDING"

    has_failure = False
    has_pending = False
    has_success = False
    real_count = 0
    for ctx in contexts:
        typename = ctx.get("__typename", "")
        if is_trivial_ctx(ctx):
            continue
        real_count += 1
        if typename == "StatusContext":
            st = (ctx.get("state") or "").upper()
            if st == "FAILURE":
                has_failure = True
            elif st == "PENDING":
                has_pending = True
            elif st == "SUCCESS":
                has_success = True
        elif typename == "CheckRun":
            conclusion = (ctx.get("conclusion") or "").upper()
            status = (ctx.get("status") or "").upper()
            if conclusion in ("FAILURE", "TIMED_OUT", "CANCELLED"):
                has_failure = True
            elif conclusion == "SUCCESS":
                has_success = True
            elif status in ("IN_PROGRESS", "QUEUED", "WAITING"):
                has_pending = True

    if real_count == 0:
        return ""
    if has_failure:
        return "FAILURE"
    if has_pending:
        return "PENDING"
    if has_success:
        return "SUCCESS"
    return ""
