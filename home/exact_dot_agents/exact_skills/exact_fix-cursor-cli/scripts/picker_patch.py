#!/usr/bin/env python3
"""Diagnose and patch cursor-agent picker bundle state.

Subcommands:
    classify <dist_package> <versions_dir> <active_version>
        Print per-file picker state and the worst state across active bundles.
        Exit 0 if all v2-good / no-anchor, 1 otherwise.

    patch <dist_package> <versions_dir> <active_version>
        Apply OLD->V2, V1->V2, and thinking-display migrations to active bundles.
        Reports per-file action taken. Dumps anchor context for unknown-shape
        files so a human or agent can re-derive the regex patterns. Exit 0.

Active bundles =
    <dist_package>/*.index.js
    + <versions_dir>/<active_version>/*.index.js
Older directories under <versions_dir> are intentionally NOT scanned.

Picker-bug semantics:
    The c() function inside the model-service webpack module fetches
    availableModels(useModelParameters:true). The bug-states this script knows:
        - old-empty-picker:      upstream as-shipped, picker EMPTY on cold start
        - v1-collapses-variants: earlier patch from this script; picker shows ALL
                                 models but thinking/non-thinking variants
                                 collapse into duplicate display names
        - v2-good:               current refined patch; prefers models with
                                 parameterDefinitions so variants render as
                                 separate entries, falls back to all models so
                                 the picker is never empty
        - display-collapses-thinking:
                                 upstream model metadata has separate thinking
                                 slugs but duplicate display names, so `/model`
                                 and the prompt footer omit the Thinking suffix
    The regex patterns are var-name-agnostic so they match across multiple
    minified webpack chunks (e.g. 730.index.js uses t/o/r, 8262.index.js uses
    n/t/l).
"""

import re
import sys
from pathlib import Path


PICKER_ANCHORS = [
    "useModelParameters:!0,doNotUseMarkdown:!0",
    "models.fetchAvailableModelsParameterized",
]

DISPLAY_ANCHORS = [
    "buildParameterizedModelMap",
]


# Capture groups:
#   A = filtered-models var (e.g. n or t)
#   B = input-container var (e.g. t or o)
#   C = exclusion-Set var   (e.g. l or r)
#   D = outer optional-chaining temp (e.g. t or o)
#   E = inner length-or-null temp    (e.g. n or t)
#   F = v2-only fresh var for the parameterized subset

PATTERN_OLD = re.compile(
    r"const (?P<A>\w+)=(?P<B>\w+)\.models\.filter\(\(e=>!(?P<C>\w+)\.has\(e\.name\)\)\);"
    r"return (?P=A)\.some\(\(e=>\{var (?P<D>\w+),(?P<E>\w+);"
    r"return\(null!==\((?P=E)=null===\((?P=D)=e\.parameterDefinitions\)\|\|void 0===(?P=D)\?void 0:(?P=D)\.length\)&&void 0!==(?P=E)\?(?P=E):0\)>0\}\)\)"
    r"\?(?P=A):void 0"
)

PATTERN_V1 = re.compile(
    r"const (?P<A>\w+)=(?P<B>\w+)\.models\.filter\(\(e=>!(?P<C>\w+)\.has\(e\.name\)\)\);"
    r"return (?P=A)\.length>0\?(?P=A):void 0"
)

PATTERN_V2 = re.compile(
    r"const (?P<A>\w+)=(?P<B>\w+)\.models\.filter\(\(e=>!(?P<C>\w+)\.has\(e\.name\)\)\);"
    r"const (?P<F>\w+)=(?P=A)\.filter\(\(e=>\{var (?P<D>\w+),(?P<E>\w+);"
    r"return\(null!==\((?P=E)=null===\((?P=D)=e\.parameterDefinitions\)\|\|void 0===(?P=D)\?void 0:(?P=D)\.length\)&&void 0!==(?P=E)\?(?P=E):0\)>0\}\)\);"
    r"return (?P=F)\.length>0\?(?P=F):(?P=A)\.length>0\?(?P=A):void 0"
)

PATTERN_DISPLAY_OLD = re.compile(
    r"buildParameterizedModelMap\((?P<A>\w+)\)\{"
    r"this\.parameterizedModelMap\.clear\(\);"
    r"for\(const (?P<B>\w+) of (?P=A)\)"
    r"(?P=B)\.name&&this\.parameterizedModelMap\.set\((?P=B)\.name,(?P=B)\)"
    r"\}"
)

PATTERN_DISPLAY_V2 = re.compile(
    r"buildParameterizedModelMap\(\w+\)\{"
    r"this\.parameterizedModelMap\.clear\(\);"
    r"for\(const \w+ of \w+\)if\(\w+\.name\)\{"
    r"const \w+=\(\w+\.name\|\|\w+\.serverModelName\|\|\"\"\)\.toLowerCase\(\),"
    r"\w+=\w+=>\{if\(!\w+\|\|\w+\.toLowerCase\(\)\.includes\(\"thinking\"\)\|\|!\w+\.includes\(\"thinking\"\)\)"
    r"return \w+;return \w+\.endsWith\(\" Fast\"\)\?\w+\.slice\(0,-5\)\+\" Thinking Fast\":\w+\+\" Thinking\"\};"
    r"\w+\.clientDisplayName=\w+\(\w+\.clientDisplayName\),"
    r"\w+\.inputboxShortModelName=\w+\(\w+\.inputboxShortModelName\),"
    r"this\.parameterizedModelMap\.set\(\w+\.name,\w+\)\}\}"
)


SEVERITY = {
    "v2-good": 0,
    "no-anchor": 0,
    "display-collapses-thinking": 1,
    "v1-collapses-variants": 1,
    "old-empty-picker": 1,
    "unknown-shape": 2,
}


def classify(source):
    if PATTERN_DISPLAY_OLD.search(source):
        return "display-collapses-thinking"
    if PATTERN_V1.search(source):
        return "v1-collapses-variants"
    if PATTERN_OLD.search(source):
        return "old-empty-picker"
    if PATTERN_V2.search(source) or PATTERN_DISPLAY_V2.search(source):
        return "v2-good"
    if any(a in source for a in PICKER_ANCHORS + DISPLAY_ANCHORS):
        return "unknown-shape"
    return "no-anchor"


def _pick_var(taken, preference):
    for cand in preference:
        if cand not in taken:
            return cand
    raise ValueError(f"no free single-letter var (taken: {sorted(taken)})")


def _build_v2(A, B, C, D, E):
    F = _pick_var({A, B, C, D, E}, ["r", "s", "u", "v", "w", "x", "y", "z", "p", "q"])
    return (
        f"const {A}={B}.models.filter((e=>!{C}.has(e.name)));"
        f"const {F}={A}.filter((e=>{{var {D},{E};"
        f"return(null!==({E}=null===({D}=e.parameterDefinitions)||void 0==={D}?void 0:{D}.length)&&void 0!=={E}?{E}:0)>0}}));"
        f"return {F}.length>0?{F}:{A}.length>0?{A}:void 0"
    )


def _migrate_old(match):
    return _build_v2(
        match.group("A"), match.group("B"), match.group("C"),
        match.group("D"), match.group("E"),
    )


def _migrate_v1(match):
    A, B, C = match.group("A"), match.group("B"), match.group("C")
    D = _pick_var({A, B, C}, ["t", "o", "n", "u", "v"])
    E = _pick_var({A, B, C, D}, ["n", "t", "o", "u", "v"])
    return _build_v2(A, B, C, D, E)


def _migrate_display(match):
    A, B = match.group("A"), match.group("B")
    id_var = _pick_var({A, B}, ["n", "r", "o", "i", "s", "a", "l", "d"])
    format_var = _pick_var({A, B, id_var}, ["r", "o", "i", "s", "a", "l", "d", "c"])
    label_var = _pick_var({A, B, id_var, format_var}, ["o", "i", "s", "a", "l", "d", "c", "u"])
    return (
        f"buildParameterizedModelMap({A}){{"
        "this.parameterizedModelMap.clear();"
        f"for(const {B} of {A})if({B}.name){{"
        f"const {id_var}=({B}.name||{B}.serverModelName||\"\").toLowerCase(),"
        f"{format_var}={label_var}=>{{"
        f"if(!{label_var}||{label_var}.toLowerCase().includes(\"thinking\")||!{id_var}.includes(\"thinking\"))return {label_var};"
        f"return {label_var}.endsWith(\" Fast\")?{label_var}.slice(0,-5)+\" Thinking Fast\":{label_var}+\" Thinking\""
        "};"
        f"{B}.clientDisplayName={format_var}({B}.clientDisplayName),"
        f"{B}.inputboxShortModelName={format_var}({B}.inputboxShortModelName),"
        f"this.parameterizedModelMap.set({B}.name,{B})"
        "}}"
    )


def patch_source(source):
    new_source, old_count = PATTERN_OLD.subn(_migrate_old, source)
    new_source, v1_count = PATTERN_V1.subn(_migrate_v1, new_source)
    new_source, display_count = PATTERN_DISPLAY_OLD.subn(_migrate_display, new_source)
    return new_source, old_count, v1_count, display_count


def dump_anchor_context(path, source, before=120, after=520):
    printed_any = False
    for anchor in PICKER_ANCHORS:
        start = 0
        while True:
            idx = source.find(anchor, start)
            if idx == -1:
                break
            ctx_start = max(0, idx - before)
            ctx_end = min(len(source), idx + len(anchor) + after)
            print(f"--- anchor in {path} (offset {idx}) ---")
            print(f"  anchor: {anchor!r}")
            print(f"  context: {source[ctx_start:ctx_end]}")
            printed_any = True
            start = idx + len(anchor)
    return printed_any


def active_bundles(dist_package, versions_dir, active_version):
    bundles = []
    if dist_package.exists() and dist_package.is_dir():
        bundles.extend(sorted(dist_package.glob("*.index.js")))
    active_versions_dir = versions_dir / active_version
    if active_versions_dir.exists() and active_versions_dir.is_dir():
        bundles.extend(sorted(active_versions_dir.glob("*.index.js")))
    seen = set()
    unique = []
    for p in bundles:
        rp = p.resolve()
        if rp in seen:
            continue
        seen.add(rp)
        unique.append(p)
    return unique


def cmd_classify(dist_package, versions_dir, active_version):
    files = active_bundles(dist_package, versions_dir, active_version)
    worst = "v2-good"
    reported = 0
    for p in files:
        state = classify(p.read_text(errors="ignore"))
        if state == "no-anchor":
            continue
        reported += 1
        print(f"FILE:{state}:{p}")
        if SEVERITY[state] > SEVERITY[worst]:
            worst = state
    print(f"REPORTED:{reported}")
    print(f"WORST:{worst}")
    return 0 if worst in ("v2-good", "no-anchor") else 1


def cmd_patch(dist_package, versions_dir, active_version):
    files = active_bundles(dist_package, versions_dir, active_version)
    patched_files = 0
    already_patched_files = 0
    unknown_files = []
    total_replacements = 0

    print("Model picker patch results:")
    for p in files:
        source = p.read_text(errors="ignore")
        state_before = classify(source)
        if state_before == "v2-good":
            already_patched_files += 1
            print(f"  already patched (v2): {p}")
            continue
        if state_before in ("display-collapses-thinking", "v1-collapses-variants", "old-empty-picker"):
            new_source, old_count, v1_count, display_count = patch_source(source)
            details = []
            if old_count > 0:
                s = "s" if old_count != 1 else ""
                details.append(f"{old_count} OLD->V2 replacement{s}")
            if v1_count > 0:
                s = "s" if v1_count != 1 else ""
                details.append(f"{v1_count} V1->V2 migration{s}")
            if display_count > 0:
                s = "s" if display_count != 1 else ""
                details.append(f"{display_count} thinking-display migration{s}")
            p.write_text(new_source)
            patched_files += 1
            total_replacements += old_count + v1_count + display_count
            print(f"  patched: {p} ({', '.join(details)})")
            continue
        if state_before == "unknown-shape":
            unknown_files.append(p)
            print(f"  unknown shape: {p}")
            continue
        # no-anchor: skip silently

    print(f"  scanned: {len(files)} active bundle files")
    print(f"  total replacements: {total_replacements}")

    if unknown_files:
        print()
        print("  Some bundles match anchors but neither known signature.")
        print("  Dumping anchor-located context for re-derivation:")
        print()
        for p in unknown_files:
            source = p.read_text(errors="ignore")
            dump_anchor_context(p, source)

    if patched_files == 0 and already_patched_files == 0 and not unknown_files:
        print("  note: No picker anchors found in any active bundle.")
        print("PATCH_STATE:no-signature")
    elif unknown_files:
        print("PATCH_STATE:unknown-shape")
    elif patched_files > 0:
        print("PATCH_STATE:patched")
    else:
        print("PATCH_STATE:already-patched")
    return 0


def main(argv):
    if len(argv) < 5:
        print(__doc__, file=sys.stderr)
        return 2
    cmd = argv[1]
    dist_package = Path(argv[2])
    versions_dir = Path(argv[3])
    active_version = argv[4]
    if cmd == "classify":
        return cmd_classify(dist_package, versions_dir, active_version)
    if cmd == "patch":
        return cmd_patch(dist_package, versions_dir, active_version)
    print(f"Error: unknown subcommand: {cmd}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
