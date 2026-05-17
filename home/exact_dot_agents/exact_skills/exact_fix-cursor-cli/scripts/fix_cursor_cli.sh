#!/usr/bin/env bash
# Description: Diagnose and repair local cursor-cli install issues (quarantine + empty /model picker).
#
# Picker-bug semantics (read this BEFORE editing OLD_C_SIGNATURE / V2_C_SIGNATURE below):
#   - File:     <dist-package>/<chunkId>.index.js (minified webpack chunk)
#   - Function: c(e,t) inside the "./src/models/model-service.ts" module.
#   - Anchor:   "useModelParameters:!0,doNotUseMarkdown:!0" is the unique protobuf
#               field block on the availableModels() call this script targets.
#   - Bug:      Upstream returns void 0 when no model has parameterDefinitions
#               yet, leaving the interactive /model picker empty in cold-start
#               sessions.
#   - Patch:    Prefer models WITH parameterDefinitions (so thinking / non-thinking
#               variants render as separate entries). Fall back to all non-excluded
#               models so the picker is never empty.
#
# When upstream changes minified shape, this script will report
# "No known picker signature found" and auto-dump anchor-located code regions.
# To re-derive: update OLD_C_SIGNATURE (as-shipped buggy form) and V2_C_SIGNATURE
# (variant-preserving patched form) in the Python heredoc below, using the dump
# as ground truth.

set -euo pipefail

usage() {
  cat <<'EOF'
Usage: fix_cursor_cli.sh [--reason auto|startup-failure|empty-picker|force] [--force]

Targeted repair script for known local Cursor CLI bundle regressions.

Modes:
  auto             Diagnose first. Apply only when known signatures are detected.
  startup-failure  Assume fresh cursor-agent startup is failing and apply both fixes.
  empty-picker     Assume interactive /model is empty and apply picker patch.
  force            Apply both fixes without diagnosis gating.

Notes:
  --force is equivalent to --reason force.
EOF
}

reason="auto"

while [ "$#" -gt 0 ]; do
  case "$1" in
    --reason)
      if [ "$#" -lt 2 ]; then
        echo "Error: --reason requires a value." >&2
        usage >&2
        exit 2
      fi
      reason="$2"
      shift 2
      ;;
    --reason=*)
      reason="${1#*=}"
      shift
      ;;
    --force)
      reason="force"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Error: unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

case "$reason" in
  auto|startup-failure|empty-picker|force) ;;
  *)
    echo "Error: invalid --reason value: $reason" >&2
    usage >&2
    exit 2
    ;;
esac

if ! command -v brew >/dev/null 2>&1; then
  echo "Error: Homebrew is required but not found on PATH." >&2
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "Error: python3 is required but not found on PATH." >&2
  exit 1
fi

if ! command -v cursor-agent >/dev/null 2>&1; then
  echo "Error: cursor-agent is required but not found on PATH." >&2
  exit 1
fi

version="$(brew list --cask --versions cursor-cli 2>/dev/null | awk '{ print $2 }')"
if [ -z "$version" ]; then
  echo "cursor-cli is not installed; nothing to fix."
  exit 0
fi

dist_package="$(brew --prefix)/Caskroom/cursor-cli/${version}/dist-package"
if [ ! -d "$dist_package" ]; then
  echo "Error: cursor-cli dist package not found at: $dist_package" >&2
  exit 1
fi

set +e
pre_version_output="$(cursor-agent --version 2>&1)"
pre_version_status=$?
pre_models_output="$(cursor-agent models 2>&1)"
pre_models_status=$?
set -e

startup_broken="false"
if [ "$pre_version_status" -ne 0 ] || [ "$pre_models_status" -ne 0 ]; then
  startup_broken="true"
fi

bundle_dump_signature="false"
if [[ "$pre_version_output" == *"/dist-package/index.js:"* ]] || [[ "$pre_models_output" == *"/dist-package/index.js:"* ]]; then
  bundle_dump_signature="true"
fi

quarantine_listing="$(xattr -lr "$dist_package" 2>/dev/null || true)"
has_quarantine="false"
if [[ "$quarantine_listing" == *"com.apple.quarantine"* ]]; then
  has_quarantine="true"
fi

need_quarantine_fix="false"
need_picker_patch="false"

case "$reason" in
  auto)
    if [ "$has_quarantine" = "true" ]; then
      need_quarantine_fix="true"
    fi
    if [ "$startup_broken" = "true" ]; then
      if [ "$bundle_dump_signature" = "true" ] || [ "$has_quarantine" = "true" ]; then
        need_picker_patch="true"
      fi
      need_quarantine_fix="true"
    fi
    ;;
  startup-failure)
    need_quarantine_fix="true"
    need_picker_patch="true"
    ;;
  empty-picker)
    if [ "$has_quarantine" = "true" ]; then
      need_quarantine_fix="true"
    fi
    need_picker_patch="true"
    ;;
  force)
    need_quarantine_fix="true"
    need_picker_patch="true"
    ;;
esac

echo "Diagnosis:"
echo "  reason: $reason"
echo "  pre cursor-agent --version exit: $pre_version_status"
echo "  pre cursor-agent models exit: $pre_models_status"
echo "  startup broken: $startup_broken"
echo "  bundle dump signature: $bundle_dump_signature"
echo "  quarantine attrs present: $has_quarantine"

if [ "$pre_version_status" -ne 0 ]; then
  echo "  version probe first line: $(printf '%s\n' "$pre_version_output" | sed -n '1p')"
fi
if [ "$pre_models_status" -ne 0 ]; then
  echo "  models probe first line: $(printf '%s\n' "$pre_models_output" | sed -n '1p')"
fi

if [ "$reason" = "auto" ] && [ "$startup_broken" = "true" ] && [ "$bundle_dump_signature" = "false" ] && [ "$has_quarantine" = "false" ]; then
  echo
  echo "Refusing automatic repair: startup failed but no known bundle/quarantine signature was detected."
  echo "Capture full failure text and inspect manually before applying this targeted patch."
  exit 1
fi

if [ "$need_quarantine_fix" = "false" ] && [ "$need_picker_patch" = "false" ]; then
  echo
  echo "No repair action taken (machine appears healthy for this targeted issue)."
  echo "If /model is empty in a fresh session while 'cursor-agent models' works, rerun with:"
  echo "  $0 --reason empty-picker"
  exit 0
fi

quarantine_result="skipped"
if [ "$need_quarantine_fix" = "true" ]; then
  # Homebrew updates can reapply quarantine attributes and break native module loading.
  xattr -dr com.apple.quarantine "$dist_package" 2>/dev/null || true

  post_quarantine_listing="$(xattr -lr "$dist_package" 2>/dev/null || true)"
  if [[ "$post_quarantine_listing" == *"com.apple.quarantine"* ]]; then
    quarantine_result="attempted-but-still-present"
  elif [ "$has_quarantine" = "true" ]; then
    quarantine_result="removed"
  else
    quarantine_result="already-clear"
  fi
fi

picker_result="skipped"
if [ "$need_picker_patch" = "true" ]; then
  picker_output="$(
    python3 - "$dist_package" "$HOME/.local/share/cursor-agent/versions" "$reason" <<'PY'
from pathlib import Path
import sys

OLD_C_SIGNATURE = "const n=t.models.filter((e=>!l.has(e.name)));return n.some((e=>{var t,n;return(null!==(n=null===(t=e.parameterDefinitions)||void 0===t?void 0:t.length)&&void 0!==n?n:0)>0}))?n:void 0"
V2_C_SIGNATURE = "const n=t.models.filter((e=>!l.has(e.name)));const r=n.filter((e=>{var t,n;return(null!==(n=null===(t=e.parameterDefinitions)||void 0===t?void 0:t.length)&&void 0!==n?n:0)>0}));return r.length>0?r:n.length>0?n:void 0"

# Anchors used to locate the picker code when exact signatures stop matching.
# These strings are upstream-stable across minifier runs (protobuf field names
# and debug-log identifiers are not renamed by the minifier).
PICKER_ANCHORS = [
    "useModelParameters:!0,doNotUseMarkdown:!0",
    "models.fetchAvailableModelsParameterized",
]


def dump_anchor_context(path, source, before=120, after=520):
    """Print code regions around each picker anchor for signature re-derivation."""
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


def collect_candidate_files(root):
    if not root.exists():
        return []
    if root.is_file():
        return [root] if root.name.endswith(".index.js") else []
    if root.name == "versions":
        files = []
        for version_dir in sorted(root.iterdir()):
            if version_dir.is_dir():
                files.extend(sorted(version_dir.glob("*.index.js")))
        return files
    return sorted(root.glob("*.index.js"))


reason = sys.argv[3]
require_match = reason == "empty-picker"
patched = 0
already_patched = 0
replacement_count = 0
candidate_files = []
seen_paths = set()

for arg in sys.argv[1:3]:
    for path in collect_candidate_files(Path(arg)):
        resolved = path.resolve()
        if resolved in seen_paths:
            continue
        seen_paths.add(resolved)
        candidate_files.append(path)

print("Model picker patch results:")
for path in candidate_files:
    source = path.read_text(errors="ignore")
    c_old_count = source.count(OLD_C_SIGNATURE)
    total_replacements = c_old_count
    if total_replacements > 0:
        patched_source = source.replace(OLD_C_SIGNATURE, V2_C_SIGNATURE)
        path.write_text(patched_source)
        patched += 1
        replacement_count += total_replacements
        suffix = "s" if c_old_count != 1 else ""
        print(f"  patched: {path} ({c_old_count} replacement{suffix})")
    elif V2_C_SIGNATURE in source:
        already_patched += 1
        print(f"  already patched: {path}")

print(f"  scanned: {len(candidate_files)} bundle files")
print(f"  total replacements: {replacement_count}")

if patched == 0 and already_patched == 0:
    print()
    print("  No known picker signature matched. Likely cause: upstream bundle")
    print("  shape changed since this skill was last updated.")
    print("  Dumping anchor-located code regions so OLD_C_SIGNATURE and")
    print("  V2_C_SIGNATURE can be re-derived. See script header for bug semantics.")
    print()
    dumped = False
    for path in candidate_files:
        source = path.read_text(errors="ignore")
        if any(anchor in source for anchor in PICKER_ANCHORS):
            if dump_anchor_context(path, source):
                dumped = True
    if not dumped:
        print("  warning: none of the picker anchors were found either.")
        print("  Anchors searched:")
        for anchor in PICKER_ANCHORS:
            print(f"    - {anchor!r}")
        print("  Inspect the bundle manually before editing this script.")
    if require_match:
        raise SystemExit("Error: no known signature; see anchor dump above.")

if patched > 0:
    print("PATCH_STATE:patched")
elif already_patched > 0:
    print("PATCH_STATE:already-patched")
else:
    print("PATCH_STATE:no-signature")
PY
  )"
  while IFS= read -r line; do
    if [[ "$line" == PATCH_STATE:* ]]; then
      picker_result="${line#PATCH_STATE:}"
      continue
    fi
    echo "$line"
  done <<< "$picker_output"
else
  echo "Model picker patch results:"
  echo "  skipped by diagnosis"
fi

set +e
post_version_output="$(cursor-agent --version 2>&1)"
post_version_status=$?
post_models_output="$(cursor-agent models 2>&1)"
post_models_status=$?
set -e

echo
echo "Repair summary:"
echo "  quarantine action: $quarantine_result"
echo "  picker patch action: $picker_result"

echo "Post-fix verification:"
echo "  cursor-agent --version exit: $post_version_status"
echo "  cursor-agent --version first line: $(printf '%s\n' "$post_version_output" | sed -n '1p')"
echo "  cursor-agent models exit: $post_models_status"
echo "  cursor-agent models first line: $(printf '%s\n' "$post_models_output" | sed -n '1p')"

echo
echo "If your issue was interactive-only (/model empty), verify in a fresh session:"
echo "  cursor-agent --force"
echo "  /model"
