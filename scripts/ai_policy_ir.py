#!/usr/bin/env python3
"""Policy IR: the rule records compile_ai_policy.py compiles into readonly_AGENTS.md.

Stage 1: one Rule per numbered SOP heading, disposition "core", consumer
"home/readonly_AGENTS.md", verbatim text -- the compiled output must equal
the legacy file byte-for-byte. Stage 2 applies a disposition override on top
of that mechanical split (see apply_dispositions/DISPOSITIONS_PATH) once a
rule has an accepted ablation/evaluation record, moving it to a smaller consumer
(skill/hook/overlay) without changing the split itself.

Reviewer note: DISPOSITIONS_PATH freezes each moved rule's original text as a
JSON-escaped string -- a normal PR diff renders that as one dense unreadable
line per rule. Do not approve a disposition-override diff from the JSON diff
alone; open the named consumer file and compare its content against the
frozen `text` field by eye (or via `compile_ai_policy.py explain <rule-id>`,
which pretty-prints one rule's frozen text) before trusting the ablation.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass, replace
from pathlib import Path

DISPOSITIONS = frozenset(
    {
        "core",
        "skill",
        "hook",
        "harness-overlay",
        "pinned-model-overlay",
        "retired-by-passing-ablation",
    }
)
RISK_TIERS = frozenset(
    {
        "safety",
        "authorization",
        "destructive",
        "publication",
        "ownership",
        "compatibility",
        "secret",
        "git-gate",
        "standard",
    }
)
RISK_TIER_BY_RULE_ID = {
    "sop.0.binding-contract": "safety",
    "sop.1.purpose-and-hierarchy": "secret",
    "sop.2.0.compatibility-gate": "compatibility",
    "sop.3.1.git-commit-and-push-safety": "git-gate",
    "sop.3.2.ownership-gate": "ownership",
    "sop.3.4.verification-loops": "safety",
    "sop.3.5.state-machine-verification": "compatibility",
    "sop.3.6.human-visible-publication": "publication",
    "sop.4.1.durable-memory": "secret",
}

DISPOSITIONS_PATH = Path("home/dot_config/ai/exact_policy-ir/readonly_policy-dispositions.v1.json")
RULE_INVENTORY_PATH = Path("home/dot_config/ai/exact_policy-ir/readonly_policy-rule-inventory.v1.json")

# Display heading number may differ from the inventory id. Inventory ids are permanent;
# a heading rename must alias to the existing id instead of minting a new one.
RULE_ID_ALIASES = {
    "sop.3.4.1.state-machine-verification": "sop.3.5.state-machine-verification",
}

# Matches "## 0. Binding Contract", "### 2.0 Compatibility Gate", etc. Stage 1
# splits strictly on these headings so every byte of the legacy file belongs
# to exactly one rule and concatenation reconstructs the file exactly.
_HEADING_RE = re.compile(r"^(#{2,3})\s+(\S+)\s+(.+)$", re.MULTILINE)
_HEADING_NUMBER_SEG_RE = re.compile(r"^(\d+)([a-zA-Z]*)$")


@dataclass(frozen=True)
class Rule:
    id: str
    text: str
    disposition: str
    consumer: str
    risk_tier: str
    eval_ref: str
    model_scope: str = "*"
    harness_scope: str = "*"

    def __post_init__(self) -> None:
        if self.disposition not in DISPOSITIONS:
            raise ValueError(f"{self.id}: unknown disposition {self.disposition!r}")
        if self.risk_tier not in RISK_TIERS:
            raise ValueError(f"{self.id}: unknown risk tier {self.risk_tier!r}")
        if not self.eval_ref:
            raise ValueError(f"{self.id}: rule has no eval_ref")

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.text.encode("utf-8")).hexdigest()


def _slug(number: str, title: str) -> str:
    number = number.rstrip(".")
    ascii_title = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode("ascii")
    words = re.sub(r"[^a-z0-9]+", "-", ascii_title.lower()).strip("-")
    raw = f"sop.{number}.{words}"
    return RULE_ID_ALIASES.get(raw, raw)


def _risk_tier_for(rule_id: str) -> str:
    return RISK_TIER_BY_RULE_ID.get(rule_id, "standard")


def _heading_order_key(number: str) -> tuple[tuple[int, ...], str]:
    numeric: list[int] = []
    suffix = ""
    for seg in number.rstrip(".").split("."):
        match = _HEADING_NUMBER_SEG_RE.fullmatch(seg)
        if match is None:
            return ((), number)
        numeric.append(int(match.group(1)))
        suffix += match.group(2)
    return (tuple(numeric), suffix)


def _rule_order_key(rule: Rule) -> tuple:
    """Sort re-synthesized split rules by the heading number in the rule text."""
    match = _HEADING_RE.search(rule.text)
    if match:
        numeric, suffix = _heading_order_key(match.group(2))
        return (numeric, suffix, rule.id)
    id_match = re.match(r"^sop\.((?:\d+\.)*\d+)", rule.id)
    if not id_match:
        return ((), "", rule.id)
    return (tuple(int(part) for part in id_match.group(1).split(".")), "", rule.id)


def split_legacy_sop(text: str) -> list[Rule]:
    """Split the legacy monolith into one opaque Rule per numbered heading.

    Text preceding the first heading (title + `---`) is folded into the first
    rule so concatenation of all rule texts equals the input byte-for-byte.
    """
    matches = list(_HEADING_RE.finditer(text))
    if not matches:
        raise ValueError("legacy SOP text has no numbered headings to split on")

    rules: list[Rule] = []
    for index, match in enumerate(matches):
        start = 0 if index == 0 else match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        chunk = text[start:end]
        number, title = match.group(2), match.group(3)
        rule_id = _slug(number, title)
        rules.append(
            Rule(
                id=rule_id,
                text=chunk,
                disposition="core",
                consumer="home/readonly_AGENTS.md",
                risk_tier=_risk_tier_for(rule_id),
                eval_ref=f"{rule_id}.stage1-opaque",
            )
        )
    return rules


def load_dispositions(repo_root: Path) -> dict[str, dict]:
    """Load the Stage 2 disposition-override map, keyed by rule id.

    Absent file means no overrides yet (pure Stage 1). Each entry may set
    disposition/consumer/risk_tier/eval_ref/model_scope/harness_scope, and
    MUST carry a frozen `text` snapshot captured at the moment the rule left
    core -- once home/readonly_AGENTS.md shrinks, that heading's source text
    is gone from the legacy file for good, so the override is the only
    remaining place the rule's original text can live.
    """
    path = repo_root / DISPOSITIONS_PATH
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))["overrides"]


def apply_dispositions(rules: list[Rule], overrides: dict[str, dict]) -> list[Rule]:
    """Apply a disposition-override map on top of the mechanical Stage 1 split.

    Overrides for rules the legacy file still contains are applied in place.
    Overrides for rules the legacy file no longer contains (already split out
    in a prior generate) are re-synthesized from their frozen `text` snapshot,
    so a rule can never silently disappear just because core has shrunk.
    """
    present_ids = {rule.id for rule in rules}
    result = []
    for rule in rules:
        override = overrides.get(rule.id)
        if override:
            if override.get("text") != rule.text:
                raise ValueError(f"{rule.id}: override frozen text does not match the source rule text")
            result.append(replace(rule, **override))
        else:
            result.append(rule)
    for rule_id, override in overrides.items():
        if rule_id not in present_ids:
            if "text" not in override:
                raise ValueError(
                    f"{rule_id}: override has no frozen text and the rule no longer exists in the legacy file"
                )
            fields = {"id": rule_id, "risk_tier": _risk_tier_for(rule_id), "eval_ref": f"{rule_id}.missing-eval-ref"}
            fields.update(override)
            result.append(Rule(**fields))
    return sorted(result, key=_rule_order_key)


def render(rules: list[Rule]) -> str:
    """Concatenate the text of every rule whose consumer is the legacy SOP file.

    Stage 1 (no overrides): every rule targets home/readonly_AGENTS.md, so this
    reproduces the legacy file byte-for-byte. Stage 2: rules retargeted to a
    different consumer (skill/hook/overlay) are excluded here -- their ablation
    record must bind the frozen rule hash to the checked consumer file hash.
    """
    return "".join(rule.text for rule in rules if rule.disposition == "core")


def load_legacy_sop(repo_root: Path) -> list[Rule]:
    legacy = repo_root / "home/readonly_AGENTS.md"
    rules = split_legacy_sop(legacy.read_text(encoding="utf-8"))
    overrides = load_dispositions(repo_root)
    inventory_path = repo_root / RULE_INVENTORY_PATH
    inventory_ids = set()
    if inventory_path.is_file():
        inventory_ids = set(json.loads(inventory_path.read_text(encoding="utf-8"))["rule_ids"])
    unknown_missing = set(overrides) - {rule.id for rule in rules} - inventory_ids
    if unknown_missing:
        raise ValueError(
            f"disposition override(s) do not match a current or inventoried rule: {sorted(unknown_missing)}"
        )
    return apply_dispositions(rules, overrides)
