#!/usr/bin/env python3
"""Harness capability snapshot: what each harness proves about policy enforcement.

Read from home/dot_config/ai/readonly_harness-capabilities.v1.json (deployed as
~/.config/ai/harness-capabilities.v1.json). Compilation must fail closed when a
rule's harness_scope names a harness missing from this snapshot, or a
hook-disposition rule targets a harness whose hook_support is below "blocking".
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

# Ordered weakest to strongest. "mutation" is the only level that proves a hook can rewrite a
# delegation payload rather than merely veto it, which is what the band gate needs; a rule that
# only has to stop something is satisfied from "blocking" up.
HOOK_SUPPORT_LEVELS = ("none", "advisory", "blocking", "mutation")
SUBAGENT_MODEL_BINDINGS = frozenset({"static", "runtime"})


def hook_support_at_least(level: str, required: str) -> bool:
    return HOOK_SUPPORT_LEVELS.index(level) >= HOOK_SUPPORT_LEVELS.index(required)


SNAPSHOT_PATH = Path("home/dot_config/ai/readonly_harness-capabilities.v1.json")


@dataclass(frozen=True)
class HarnessCapability:
    harness: str
    version_evidence: str
    instruction_entrypoints: tuple[str, ...]
    hook_support: str
    model_mutable: bool
    subagent_model_binding: str
    evidence_freshness: str
    # Empty unless hook_support is "mutation", where __post_init__ requires it: a hook that can
    # rewrite a call has to say which fields, so "mutation" cannot be read as "rewrites anything".
    mutation_scope: str = ""

    def __post_init__(self) -> None:
        if self.hook_support not in HOOK_SUPPORT_LEVELS:
            raise ValueError(f"{self.harness}: unknown hook_support {self.hook_support!r}")
        if self.subagent_model_binding not in SUBAGENT_MODEL_BINDINGS:
            raise ValueError(f"{self.harness}: unknown subagent_model_binding {self.subagent_model_binding!r}")
        if self.hook_support == "mutation" and not self.mutation_scope:
            raise ValueError(f"{self.harness}: mutation hook support must name what the hook may rewrite")


def load_snapshot_path(path: Path) -> dict[str, HarnessCapability]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    snapshot: dict[str, HarnessCapability] = {}
    for entry in raw["harnesses"]:
        capability = HarnessCapability(
            harness=entry["harness"],
            version_evidence=entry["version_evidence"],
            instruction_entrypoints=tuple(entry["instruction_entrypoints"]),
            hook_support=entry["hook_support"],
            model_mutable=entry["model_mutable"],
            subagent_model_binding=entry["subagent_model_binding"],
            mutation_scope=entry.get("mutation_scope", ""),
            evidence_freshness=entry["evidence_freshness"],
        )
        snapshot[capability.harness] = capability
    return snapshot


def load_snapshot(repo_root: Path) -> dict[str, HarnessCapability]:
    return load_snapshot_path(repo_root / SNAPSHOT_PATH)


class UnsupportedCapabilityError(ValueError):
    """A rule relies on a harness capability the snapshot does not prove."""


def check_rule_capability(rule, snapshot: dict[str, "HarnessCapability"]) -> None:
    if rule.disposition == "hook" and rule.harness_scope == "*":
        raise UnsupportedCapabilityError(f"{rule.id}: hook disposition requires an explicit harness_scope")
    if rule.disposition == "pinned-model-overlay":
        if rule.harness_scope == "*":
            raise UnsupportedCapabilityError(f"{rule.id}: pinned-model-overlay requires an explicit harness_scope")
        if rule.model_scope == "*":
            raise UnsupportedCapabilityError(f"{rule.id}: pinned-model-overlay requires an explicit model_scope")
    if rule.harness_scope == "*":
        return
    capability = snapshot.get(rule.harness_scope)
    if capability is None:
        raise UnsupportedCapabilityError(f"{rule.id}: harness {rule.harness_scope!r} has no capability snapshot entry")
    if rule.disposition == "hook" and not hook_support_at_least(capability.hook_support, "blocking"):
        raise UnsupportedCapabilityError(
            f"{rule.id}: hook disposition requires blocking hook support on {rule.harness_scope!r}, "
            f"got {capability.hook_support!r}"
        )
