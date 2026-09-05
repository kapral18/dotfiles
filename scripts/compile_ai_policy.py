#!/usr/bin/env python3
"""Deterministic, network-free compiler for the SOP policy IR.

Stage 1: compiles home/readonly_AGENTS.md byte-for-byte from one opaque rule
per numbered heading (see ai_policy_ir.py). No semantic splitting happens yet
-- audit-coverage exists precisely so a future split cannot silently drop
content: every legacy heading must map to a disposed, consumed, eval-refed
rule before it may be split out of core.

Usage:
    compile_ai_policy.py generate [--repo-root PATH]
    compile_ai_policy.py verify [--all-targets] [--repo-root PATH]
    compile_ai_policy.py verify-budgets --core-max-bytes N --overlay-max-bytes N
        --skill-max-bytes N --description-total-max-bytes N [--repo-root PATH]
    compile_ai_policy.py audit-coverage --legacy PATH [--manifest PATH] [--base-inventory PATH | --base-ref REF] [--repo-root PATH]
    compile_ai_policy.py explain RULE_ID [--repo-root PATH]
    compile_ai_policy.py measure [--repo-root PATH]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import ai_harness_capabilities as capabilities
import ai_policy_ir as ir

MANIFEST_PATH = Path("home/dot_config/ai/exact_policy-ir/readonly_policy-manifest.v1.json")
LEGACY_PATH = Path("home/readonly_AGENTS.md")
SKILLS_ROOT = Path("home/exact_dot_agents/exact_skills")
MANIFEST_VERSION = 1
PROTECTED_CORE_RULE_IDS = frozenset(
    {
        "sop.0.binding-contract",
        "sop.2.1.compatibility-gate",
        "sop.3.2.git-commit-and-push-safety",
        "sop.3.3.ownership-gate",
        "sop.3.5.verification-loops",
        "sop.3.6.state-machine-verification",
        "sop.3.7.delegation-categories",
        "sop.3.8.human-visible-publication",
        "sop.4.1.durable-memory",
    }
)
NAME_PREFIXES = ("readonly_", "private_", "executable_")


def _deployed_basename(path: Path) -> str:
    name = path.name
    for prefix in NAME_PREFIXES:
        if name.startswith(prefix):
            name = name[len(prefix) :]
    return name


def _atomic_replace(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f"{path.name}.", dir=path.parent)
    temporary_path = Path(temporary)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, path)
    except BaseException:
        try:
            os.close(fd)
        except OSError:
            pass
        temporary_path.unlink(missing_ok=True)
        raise


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _rule_identity_title(rule: ir.Rule) -> str | None:
    match = ir._HEADING_RE.search(rule.text)
    if not match:
        return None
    title = match.group(3).lower()
    title = re.sub(r"\s*\(hard requirement\)", "", title)
    return re.sub(r"[^a-z0-9]+", "-", title).strip("-")


def _rule_identity_title_from_id(rule_id: str) -> str:
    parts = rule_id.split(".")
    while parts and (parts[0] == "sop" or re.fullmatch(r"\d+[a-z]?", parts[0])):
        parts.pop(0)
    title = ".".join(parts)
    return re.sub(r"-hard-requirement$", "", title)


def _build_manifest(rules: list[ir.Rule], rendered: str) -> dict:
    return {
        "version": MANIFEST_VERSION,
        "output_path": str(LEGACY_PATH),
        "output_sha256": _sha256_bytes(rendered.encode("utf-8")),
        "output_bytes": len(rendered.encode("utf-8")),
        "rules": [
            {
                "id": rule.id,
                "sha256": rule.sha256,
                "bytes": len(rule.text.encode("utf-8")),
                "disposition": rule.disposition,
                "consumer": rule.consumer,
                "risk_tier": rule.risk_tier,
                "eval_ref": rule.eval_ref,
                "model_scope": rule.model_scope,
                "harness_scope": rule.harness_scope,
            }
            for rule in rules
        ],
    }


def _load_manifest(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_policy_audit(repo_root: Path) -> dict:
    path = repo_root / ir.POLICY_AUDIT_PATH
    if not path.is_file():
        return {"version": 1, "overrides": {}, "ablations": {}}
    audit = json.loads(path.read_text(encoding="utf-8"))
    audit.setdefault("overrides", {})
    audit.setdefault("ablations", {})
    return audit


def _check_capabilities(rules: list[ir.Rule], repo_root: Path) -> None:
    snapshot = capabilities.load_snapshot(repo_root)
    for rule in rules:
        capabilities.check_rule_capability(rule, snapshot)


def _iter_skill_descriptions(repo_root: Path, *, non_manual_only: bool = False):
    """Yield source byte counts; invocation metadata does not prove native visibility."""
    skills_root = repo_root / SKILLS_ROOT
    if not skills_root.is_dir():
        return
    for skill_dir in sorted(p for p in skills_root.iterdir() if p.is_dir()):
        entry = next(
            (skill_dir / c for c in ("readonly_SKILL.md", "SKILL.md") if (skill_dir / c).is_file()),
            None,
        )
        if entry is None:
            continue
        frontmatter = entry.read_text(encoding="utf-8").split("---", 2)
        if non_manual_only and len(frontmatter) >= 2 and "disable-model-invocation: true" in frontmatter[1]:
            continue
        description_bytes = 0
        if len(frontmatter) >= 2:
            match = re.search(r'^description:\s*"?(?P<desc>[^"\n]+)"?$', frontmatter[1], re.MULTILINE)
            if match:
                description_bytes = len(match.group("desc").encode("utf-8"))
        yield entry, entry.stat().st_size, description_bytes


def cmd_generate(args: argparse.Namespace) -> int:
    repo_root: Path = args.repo_root
    source_rule_ids = {rule.id for rule in ir.split_legacy_sop((repo_root / LEGACY_PATH).read_text(encoding="utf-8"))}
    rules = ir.load_legacy_sop(repo_root)
    _check_capabilities(rules, repo_root)
    rendered = ir.render(rules)

    legacy_path = repo_root / LEGACY_PATH
    current = legacy_path.read_text(encoding="utf-8") if legacy_path.is_file() else None
    if current != rendered:
        _atomic_replace(legacy_path, rendered.encode("utf-8"))
        print(f"generate: wrote {legacy_path} ({len(rendered.encode('utf-8'))} bytes)")
    else:
        print(f"generate: {legacy_path} unchanged, skipped write")

    manifest = _build_manifest(rules, rendered)
    manifest_path = repo_root / MANIFEST_PATH
    manifest_bytes = (json.dumps(manifest, indent=2, sort_keys=False) + "\n").encode("utf-8")
    existing_manifest = manifest_path.read_bytes() if manifest_path.is_file() else None
    if existing_manifest != manifest_bytes:
        _atomic_replace(manifest_path, manifest_bytes)
        print(f"generate: wrote {manifest_path}")
    else:
        print(f"generate: {manifest_path} unchanged, skipped write")

    inventory_path = repo_root / ir.RULE_INVENTORY_PATH
    inventory = {"version": 1, "rule_ids": []}
    if inventory_path.is_file():
        inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    known_ids = set(inventory["rule_ids"])
    new_ids = source_rule_ids - known_ids
    if new_ids:
        inventory["rule_ids"] = sorted(known_ids | new_ids)
        inventory_bytes = (json.dumps(inventory, indent=2) + "\n").encode("utf-8")
        _atomic_replace(inventory_path, inventory_bytes)
        print(f"generate: appended {len(new_ids)} new rule id(s) to {inventory_path}: {sorted(new_ids)}")
    return 0


def _load_rules_from_legacy_path(repo_root: Path, legacy_path: Path) -> list[ir.Rule]:
    if legacy_path == LEGACY_PATH:
        return ir.load_legacy_sop(repo_root)
    rules = ir.split_legacy_sop((repo_root / legacy_path).read_text(encoding="utf-8"))
    return ir.apply_dispositions(rules, ir.load_dispositions(repo_root))


def cmd_verify(args: argparse.Namespace) -> int:
    repo_root: Path = args.repo_root
    legacy_rel = getattr(args, "legacy", LEGACY_PATH)
    manifest_rel = getattr(args, "manifest", None)
    rules = _load_rules_from_legacy_path(repo_root, legacy_rel)
    _check_capabilities(rules, repo_root)
    rendered = ir.render(rules)

    legacy_path = repo_root / legacy_rel
    on_disk = legacy_path.read_text(encoding="utf-8") if legacy_path.is_file() else ""
    if rendered != on_disk:
        print(f"verify: {legacy_path} does not match compiled output (drift detected)", file=sys.stderr)
        return 1

    expected_manifest = _build_manifest(rules, rendered)
    manifest = expected_manifest
    if manifest_rel is not None:
        manifest_path = repo_root / manifest_rel
        manifest = _load_manifest(manifest_path)
        if manifest != expected_manifest:
            print(f"verify: {manifest_path} does not match the recompiled manifest", file=sys.stderr)
            return 1

    manifest_rules = manifest.get("rules", [])
    for recorded in manifest_rules:
        consumer = recorded.get("consumer")
        if consumer and not (repo_root / consumer).exists():
            print(f"verify: rule {recorded['id']} consumer {consumer} does not exist", file=sys.stderr)
            return 1

    if args.all_targets:
        ablations = _load_policy_audit(repo_root).get("ablations", {})
        for recorded in manifest_rules:
            if recorded.get("disposition") == "core":
                continue
            ablation = ablations.get(recorded["id"])
            if ablation is None or ablation.get("status") not in {"passed", "mechanical-only"}:
                print(f"verify: rule {recorded['id']} has no acceptable ablation record", file=sys.stderr)
                return 1
            if ablation.get("consumer") != recorded.get("consumer"):
                print(f"verify: rule {recorded['id']} ablation consumer does not match manifest", file=sys.stderr)
                return 1
            if ablation.get("target_disposition") != recorded.get("disposition"):
                print(f"verify: rule {recorded['id']} ablation disposition does not match manifest", file=sys.stderr)
                return 1
            if ablation.get("eval_ref") != recorded.get("eval_ref"):
                print(f"verify: rule {recorded['id']} ablation eval_ref does not match manifest", file=sys.stderr)
                return 1
            if ablation.get("rule_sha256") != recorded.get("sha256"):
                print(f"verify: rule {recorded['id']} ablation rule_sha256 does not match manifest", file=sys.stderr)
                return 1
            if recorded.get("disposition") != "retired-by-passing-ablation":
                consumer_hash = _sha256_bytes((repo_root / recorded["consumer"]).read_bytes())
                if ablation.get("consumer_sha256") != consumer_hash:
                    print(
                        f"verify: rule {recorded['id']} ablation consumer_sha256 does not match current consumer",
                        file=sys.stderr,
                    )
                    return 1

    print("verify: compiled output, manifest, and rule consumers are all consistent")
    return 0


def cmd_verify_budgets(args: argparse.Namespace) -> int:
    repo_root: Path = args.repo_root
    legacy_path = repo_root / LEGACY_PATH
    core_bytes = legacy_path.stat().st_size if legacy_path.is_file() else 0
    ok = True

    print(f"verify-budgets: core {core_bytes} bytes (max {args.core_max_bytes})")
    if core_bytes > args.core_max_bytes:
        print(f"verify-budgets: core exceeds budget by {core_bytes - args.core_max_bytes} bytes", file=sys.stderr)
        ok = False

    overlay_consumers = set()
    rules = ir.load_legacy_sop(repo_root)
    manifest = _build_manifest(rules, ir.render(rules))
    overlay_consumers = {
        record["consumer"]
        for record in manifest.get("rules", [])
        if record["disposition"] in {"harness-overlay", "pinned-model-overlay"}
    }
    for consumer in sorted(overlay_consumers):
        overlay_path = repo_root / consumer
        if not overlay_path.is_file():
            print(f"verify-budgets: overlay consumer {consumer} is missing", file=sys.stderr)
            ok = False
            continue
        size = overlay_path.stat().st_size
        if size > args.overlay_max_bytes:
            print(f"verify-budgets: {consumer} is {size} bytes (max {args.overlay_max_bytes})")
            ok = False

    description_total = 0
    for entry, size, description_bytes in _iter_skill_descriptions(repo_root, non_manual_only=True):
        if size > args.skill_max_bytes:
            print(f"verify-budgets: {entry.relative_to(repo_root)} is {size} bytes (max {args.skill_max_bytes})")
            ok = False
        description_total += description_bytes

    print(
        f"verify-budgets: declared non-manual descriptions {description_total} bytes "
        f"(max {args.description_total_max_bytes})"
    )
    all_descriptions = sum(desc for _, _, desc in _iter_skill_descriptions(repo_root))
    print(f"verify-budgets: all declared descriptions {all_descriptions} bytes (native visibility not measured)")
    if description_total > args.description_total_max_bytes:
        print("verify-budgets: description total exceeds budget", file=sys.stderr)
        ok = False

    return 0 if ok else 1


def cmd_audit_coverage(args: argparse.Namespace) -> int:
    repo_root: Path = args.repo_root

    # audit-coverage must never run meaningfully without verify's drift/hash check:
    # otherwise legacy content, the inventory, and the manifest could all be
    # tampered with in the same commit and coverage would look clean by
    # comparing them only to each other, never to the compiled-from-source truth.
    verify_args = argparse.Namespace(repo_root=repo_root, all_targets=True, legacy=args.legacy, manifest=args.manifest)
    verify_exit = cmd_verify(verify_args)
    if verify_exit != 0:
        print("audit-coverage: aborting, `verify` failed first (see above)", file=sys.stderr)
        return verify_exit

    legacy_text = (repo_root / args.legacy).read_text(encoding="utf-8")
    legacy_rules = ir.split_legacy_sop(legacy_text)
    legacy_ids = {rule.id for rule in legacy_rules}

    inventory_path = repo_root / ir.RULE_INVENTORY_PATH
    if not inventory_path.is_file():
        print(
            f"audit-coverage: {inventory_path} missing; current and disposed policy rules must be recorded there",
            file=sys.stderr,
        )
        return 2
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    inventory_ids = set(inventory["rule_ids"])
    removed_rule_hashes = set(inventory.get("removed_rule_sha256", []))
    base_inventory = getattr(args, "base_inventory", None)
    base_ref = getattr(args, "base_ref", None)
    base_ids = None
    base_rules_by_id = {}
    if base_inventory:
        base_ids = set(json.loads((repo_root / base_inventory).read_text(encoding="utf-8"))["rule_ids"])
    elif base_ref:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "show", f"{base_ref}:{ir.RULE_INVENTORY_PATH}"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            base_ids = set(json.loads(result.stdout)["rule_ids"])
        legacy_result = subprocess.run(
            ["git", "-C", str(repo_root), "show", f"{base_ref}:{LEGACY_PATH}"],
            capture_output=True,
            text=True,
            check=False,
        )
        if legacy_result.returncode == 0:
            base_rules = ir.split_legacy_sop(legacy_result.stdout)
            base_rules_by_id = {rule.id: rule for rule in base_rules}
            if base_ids is None:
                base_ids = set(base_rules_by_id)
    if base_ids is not None:
        removed_ids = base_ids - inventory_ids
        current_rule_titles = {title for rule in legacy_rules if (title := _rule_identity_title(rule))}
        unaccounted_removed = []
        for rule_id in sorted(removed_ids):
            rule = base_rules_by_id.get(rule_id)
            removed_title = _rule_identity_title(rule) if rule is not None else _rule_identity_title_from_id(rule_id)
            same_rule_title_is_current = removed_title in current_rule_titles
            removed_content_is_recorded = rule is not None and rule.sha256 in removed_rule_hashes
            if rule_id in PROTECTED_CORE_RULE_IDS or not (same_rule_title_is_current or removed_content_is_recorded):
                unaccounted_removed.append(rule_id)
        if unaccounted_removed:
            print(
                f"audit-coverage: current rule inventory removed {len(unaccounted_removed)} id(s) from the base inventory: "
                f"{unaccounted_removed}",
                file=sys.stderr,
            )
            return 1
    new_from_legacy = legacy_ids - inventory_ids
    if new_from_legacy:
        print(
            f"audit-coverage: {len(new_from_legacy)} rule id(s) in {args.legacy} are missing from the "
            f"rule inventory {ir.RULE_INVENTORY_PATH}: {sorted(new_from_legacy)}",
            file=sys.stderr,
        )
        return 1
    required_ids = inventory_ids

    if args.manifest is not None:
        manifest_path = repo_root / args.manifest
        if not manifest_path.is_file():
            print(f"audit-coverage: {manifest_path} missing", file=sys.stderr)
            return 2
        manifest = _load_manifest(manifest_path)
    else:
        rules = _load_rules_from_legacy_path(repo_root, args.legacy)
        manifest = _build_manifest(rules, ir.render(rules))
    manifest_records = manifest.get("rules", [])
    manifest_ids = {record["id"] for record in manifest_records}

    seen_ids: set[str] = set()
    duplicate_ids: set[str] = set()
    for record in manifest_records:
        if record["id"] in seen_ids:
            duplicate_ids.add(record["id"])
        seen_ids.add(record["id"])
    if duplicate_ids:
        print(
            f"audit-coverage: {len(duplicate_ids)} duplicate rule id(s) in manifest: {sorted(duplicate_ids)}",
            file=sys.stderr,
        )
        return 1

    uncovered = sorted(required_ids - manifest_ids)
    if uncovered:
        print(
            f"audit-coverage: {len(uncovered)} rule(s) from the rule inventory missing from the manifest "
            f"(never omit a rule that ever existed, even across a Stage 2 split): {uncovered}",
            file=sys.stderr,
        )
        return 1

    extra = sorted(manifest_ids - required_ids)
    if extra:
        print(
            f"audit-coverage: {len(extra)} manifest rule(s) are missing from the rule inventory: {extra}",
            file=sys.stderr,
        )
        return 1

    problems = []
    for record in manifest_records:
        if record["disposition"] not in ir.DISPOSITIONS:
            problems.append(f"{record['id']}: invalid disposition {record['disposition']!r}")
        if not record.get("consumer"):
            problems.append(f"{record['id']}: no consumer")
        if not record.get("eval_ref"):
            problems.append(f"{record['id']}: no eval_ref")
        if record["disposition"] == "retired-by-passing-ablation" and not record.get("eval_ref", "").endswith(
            ".ablation-passed"
        ):
            problems.append(f"{record['id']}: retired without a recorded passing ablation eval_ref")
        if record["id"] in PROTECTED_CORE_RULE_IDS and record["disposition"] != "core":
            problems.append(f"{record['id']}: protected pre-skill lifecycle gate must stay core")

    if problems:
        print(f"audit-coverage: {len(problems)} rule(s) with incomplete disposition:", file=sys.stderr)
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        return 1

    print(f"audit-coverage: all {len(required_ids)} inventoried rules covered with valid dispositions")
    return 0


def cmd_explain(args: argparse.Namespace) -> int:
    repo_root: Path = args.repo_root
    rules = ir.load_legacy_sop(repo_root)
    for rule in rules:
        if rule.id == args.rule_id:
            print(
                json.dumps(
                    {
                        "id": rule.id,
                        "disposition": rule.disposition,
                        "consumer": rule.consumer,
                        "risk_tier": rule.risk_tier,
                        "eval_ref": rule.eval_ref,
                        "model_scope": rule.model_scope,
                        "harness_scope": rule.harness_scope,
                        "sha256": rule.sha256,
                        "text": rule.text,
                    },
                    indent=2,
                )
            )
            return 0
    print(f"explain: no rule with id {args.rule_id!r}", file=sys.stderr)
    return 1


def cmd_measure(args: argparse.Namespace) -> int:
    repo_root: Path = args.repo_root
    legacy_path = repo_root / LEGACY_PATH
    core_bytes = legacy_path.stat().st_size if legacy_path.is_file() else 0

    description_bytes = sum(desc for _, _, desc in _iter_skill_descriptions(repo_root))

    report = {
        "measurement_basis": "UTF-8 source bytes for core SOP and declared skill descriptions; not live prompt tokens or skill bodies",
        "repo_controlled_bytes": {
            "core_sop": core_bytes,
            "skill_descriptions": description_bytes,
            "total": core_bytes + description_bytes,
        },
        "declared_non_manual_description_bytes": sum(
            desc for _, _, desc in _iter_skill_descriptions(repo_root, non_manual_only=True)
        ),
        "uncontrolled_unknown": [
            "harness-specific skill description visibility",
            "harness-owned system prompt",
            "tool schemas",
            "conversation history",
            "provider tokenization",
        ],
    }
    print(json.dumps(report, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    repo_root_parent = argparse.ArgumentParser(add_help=False)
    repo_root_parent.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parent.parent)

    parser = argparse.ArgumentParser(description="Deterministic SOP policy compiler", parents=[repo_root_parent])
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("generate", parents=[repo_root_parent])

    verify = sub.add_parser("verify", parents=[repo_root_parent])
    verify.add_argument("--all-targets", action="store_true")
    verify.add_argument("--manifest", type=Path)

    budgets = sub.add_parser("verify-budgets", parents=[repo_root_parent])
    budgets.add_argument("--core-max-bytes", type=int, required=True)
    budgets.add_argument("--overlay-max-bytes", type=int, required=True)
    budgets.add_argument("--skill-max-bytes", type=int, required=True)
    budgets.add_argument("--description-total-max-bytes", type=int, required=True)

    audit = sub.add_parser("audit-coverage", parents=[repo_root_parent])
    audit.add_argument("--legacy", type=Path, required=True)
    audit.add_argument("--manifest", type=Path)
    audit.add_argument("--base-inventory", type=Path)
    audit.add_argument("--base-ref")

    explain = sub.add_parser("explain", parents=[repo_root_parent])
    explain.add_argument("rule_id")

    sub.add_parser("measure", parents=[repo_root_parent])

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.repo_root = args.repo_root.resolve()

    try:
        if args.cmd == "generate":
            return cmd_generate(args)
        if args.cmd == "verify":
            return cmd_verify(args)
        if args.cmd == "verify-budgets":
            return cmd_verify_budgets(args)
        if args.cmd == "audit-coverage":
            return cmd_audit_coverage(args)
        if args.cmd == "explain":
            return cmd_explain(args)
        if args.cmd == "measure":
            return cmd_measure(args)
    except (ValueError, OSError, capabilities.UnsupportedCapabilityError) as err:
        print(f"error: {err}", file=sys.stderr)
        return 1
    parser.error(f"unknown command {args.cmd!r}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
