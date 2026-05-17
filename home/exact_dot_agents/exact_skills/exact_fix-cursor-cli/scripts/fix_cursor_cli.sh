#!/usr/bin/env bash
# Description: Diagnose and repair local cursor-cli install issues
#              (macOS quarantine + empty / duplicate /model picker).
#
# Picker semantics: see scripts/picker_patch.py (docstring + regex patterns).
#   - old-empty-picker      -> picker EMPTY on cold start
#   - v1-collapses-variants -> picker shows DUPLICATES (thinking/non-thinking collapse)
#   - v2-good               -> variants render correctly
#
# Active bundles only:
#   <Caskroom>/<ver>/dist-package/*.index.js
#   ~/.local/share/cursor-agent/versions/<ver>/*.index.js (same ver as Caskroom)
# Older directories under ~/.local/share/cursor-agent/versions/ are ignored.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PICKER_PATCH="${SCRIPT_DIR}/picker_patch.py"

usage() {
  cat <<'EOF'
Usage: fix_cursor_cli.sh [--reason auto|startup-failure|empty-picker|force|check] [--force]

Targeted repair script for known local Cursor CLI bundle regressions.

Modes:
  auto             Diagnose first. Apply only when known picker signatures
                   (OLD or V1) or quarantine attrs are detected on active bundles.
  startup-failure  Assume fresh cursor-agent startup is failing; apply both fixes.
  empty-picker     Assume interactive /model is empty OR shows duplicate variants;
                   apply picker patch (and quarantine fix if quarantine present).
  force            Apply both fixes without diagnosis gating.
  check            Read-only. Report picker bundle state per active bundle and
                   exit non-zero if anything other than v2-good is detected.

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
  auto|startup-failure|empty-picker|force|check) ;;
  *)
    echo "Error: invalid --reason value: $reason" >&2
    usage >&2
    exit 2
    ;;
esac

for tool in brew python3 cursor-agent; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    echo "Error: $tool is required but not found on PATH." >&2
    exit 1
  fi
done

if [ ! -f "$PICKER_PATCH" ]; then
  echo "Error: picker_patch.py helper not found at: $PICKER_PATCH" >&2
  echo "If this script was just deployed, try: chezmoi apply --no-tty" >&2
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

versions_dir="$HOME/.local/share/cursor-agent/versions"

# Read-only diagnostic probes.
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
if [[ "$pre_version_output" == *"/dist-package/index.js:"* ]] || \
   [[ "$pre_models_output" == *"/dist-package/index.js:"* ]]; then
  bundle_dump_signature="true"
fi

quarantine_listing="$(xattr -lr "$dist_package" 2>/dev/null || true)"
has_quarantine="false"
if [[ "$quarantine_listing" == *"com.apple.quarantine"* ]]; then
  has_quarantine="true"
fi

# Classify picker state across active bundles.
set +e
picker_state_output="$(python3 "$PICKER_PATCH" classify "$dist_package" "$versions_dir" "$version")"
set -e
worst_picker_state="$(printf '%s\n' "$picker_state_output" | sed -n 's/^WORST:\(.*\)$/\1/p' | head -1)"
worst_picker_state="${worst_picker_state:-unknown}"

echo "Diagnosis:"
echo "  reason: $reason"
echo "  cursor-cli version: $version"
echo "  pre cursor-agent --version exit: $pre_version_status"
echo "  pre cursor-agent models exit: $pre_models_status"
echo "  startup broken: $startup_broken"
echo "  bundle dump signature: $bundle_dump_signature"
echo "  quarantine attrs present: $has_quarantine"
echo "  picker bundle state (worst): $worst_picker_state"

if [ "$pre_version_status" -ne 0 ]; then
  echo "  version probe first line: $(printf '%s\n' "$pre_version_output" | sed -n '1p')"
fi
if [ "$pre_models_status" -ne 0 ]; then
  echo "  models probe first line: $(printf '%s\n' "$pre_models_output" | sed -n '1p')"
fi

echo
echo "Picker bundle state per active file:"
state_lines="$(printf '%s\n' "$picker_state_output" | sed -n 's/^FILE:\(.*\)$/\1/p')"
if [ -z "$state_lines" ]; then
  echo "  (no active bundles with picker anchors detected)"
else
  printf '%s\n' "$state_lines" | while IFS=: read -r state path; do
    case "$state" in
      v2-good)               note="variants render correctly" ;;
      v1-collapses-variants) note="thinking/non-thinking show as DUPLICATES in /model" ;;
      old-empty-picker)      note="/model picker will be EMPTY in cold-start sessions" ;;
      unknown-shape)         note="picker anchors found but neither known signature matches" ;;
      *)                     note="$state" ;;
    esac
    echo "  $state: $path"
    echo "    -> $note"
  done
fi

if [ "$reason" = "check" ]; then
  echo
  case "$worst_picker_state" in
    v2-good|no-anchor)
      echo "Check OK: all active picker bundles are in v2-good state."
      exit 0
      ;;
    v1-collapses-variants)
      echo "Check FAIL: at least one active bundle is in V1 state (variants collapse to duplicates)."
      echo "Run: $0 --reason empty-picker"
      exit 1
      ;;
    old-empty-picker)
      echo "Check FAIL: at least one active bundle is in OLD state (empty picker)."
      echo "Run: $0 --reason empty-picker"
      exit 1
      ;;
    unknown-shape)
      echo "Check FAIL: at least one active bundle matched picker anchors but neither known signature."
      echo "Run: $0 --reason empty-picker for the anchor-context dump for re-derivation."
      exit 1
      ;;
    *)
      echo "Check FAIL: picker state could not be classified."
      exit 1
      ;;
  esac
fi

need_quarantine_fix="false"
need_picker_patch="false"

case "$reason" in
  auto)
    if [ "$has_quarantine" = "true" ]; then
      need_quarantine_fix="true"
    fi
    case "$worst_picker_state" in
      v1-collapses-variants|old-empty-picker)
        need_picker_patch="true"
        ;;
    esac
    if [ "$startup_broken" = "true" ]; then
      need_quarantine_fix="true"
      if [ "$bundle_dump_signature" = "true" ] || [ "$has_quarantine" = "true" ]; then
        need_picker_patch="true"
      fi
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

if [ "$reason" = "auto" ] && \
   [ "$startup_broken" = "true" ] && \
   [ "$bundle_dump_signature" = "false" ] && \
   [ "$has_quarantine" = "false" ] && \
   [ "$worst_picker_state" != "v1-collapses-variants" ] && \
   [ "$worst_picker_state" != "old-empty-picker" ]; then
  echo
  echo "Refusing automatic repair: startup failed but no known bundle/quarantine signature was detected."
  echo "Capture full failure text and inspect manually before applying this targeted patch."
  exit 1
fi

if [ "$need_quarantine_fix" = "false" ] && [ "$need_picker_patch" = "false" ]; then
  echo
  echo "No repair action taken (machine appears healthy for this targeted issue)."
  echo "If /model is empty or shows duplicate variants in a fresh session, rerun with:"
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
  patch_output="$(python3 "$PICKER_PATCH" patch "$dist_package" "$versions_dir" "$version")"
  while IFS= read -r line; do
    if [[ "$line" == PATCH_STATE:* ]]; then
      picker_result="${line#PATCH_STATE:}"
      continue
    fi
    echo "$line"
  done <<< "$patch_output"
fi

set +e
post_version_output="$(cursor-agent --version 2>&1)"
post_version_status=$?
post_models_output="$(cursor-agent models 2>&1)"
post_models_status=$?
post_picker_state_output="$(python3 "$PICKER_PATCH" classify "$dist_package" "$versions_dir" "$version")"
set -e

post_worst_picker_state="$(printf '%s\n' "$post_picker_state_output" | sed -n 's/^WORST:\(.*\)$/\1/p' | head -1)"
post_worst_picker_state="${post_worst_picker_state:-unknown}"

echo
echo "Repair summary:"
echo "  quarantine action: $quarantine_result"
echo "  picker patch action: $picker_result"

echo "Post-fix verification:"
echo "  cursor-agent --version exit: $post_version_status"
echo "  cursor-agent --version first line: $(printf '%s\n' "$post_version_output" | sed -n '1p')"
echo "  cursor-agent models exit: $post_models_status"
echo "  cursor-agent models first line: $(printf '%s\n' "$post_models_output" | sed -n '1p')"
echo "  picker bundle state (worst): $post_worst_picker_state"

echo
echo "If your issue was interactive-only (/model empty or duplicates), verify in a fresh session:"
echo "  cursor-agent --force"
echo "  /model"
