#!/usr/bin/env bash
# Description: Sync fish history via 1Password CLI (chronological)

set -euo pipefail

history_file="$HOME/.local/share/fish/fish_history"
item_name="fish-history-sync"

# Private scratch dir (avoids predictable /tmp paths for files that may
# contain secrets) cleaned up on any exit.
tmp_dir="$(mktemp -d "${TMPDIR:-/tmp}/fish-history-sync.XXXXXX")"
temp_file="$tmp_dir/remote"
merged_file="$tmp_dir/merged"
op_err="$tmp_dir/op_err"
cleanup() { rm -rf "$tmp_dir"; }
trap cleanup EXIT

# Check if op CLI is available and authenticated
if ! command -v op &> /dev/null; then
  echo "1Password CLI not found. Install with: brew install 1password-cli"
  exit 1
fi

if ! op account get > /dev/null 2>&1; then
  echo "1Password CLI not authenticated. Run: op signin"
  exit 1
fi

# Pull remote history from 1Password
if op document get "$item_name" --out-file "$temp_file" 2> "$op_err"; then
  # Verify remote file integrity
  if [ ! -s "$temp_file" ] || ! grep -q "^- cmd:" "$temp_file"; then
    echo "Remote history appears corrupted, skipping sync"
    exit 1
  fi

  # Merge histories using external Python script
  merge_script="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/fish-history-merge.py"
  if ! "$merge_script" "$history_file" "$temp_file" "$merged_file"; then
    echo "Failed to merge histories"
    exit 1
  fi
  if [ ! -s "$merged_file" ]; then
    echo "Failed to merge histories"
    exit 1
  fi

  # Never shrink the synced history below the remote copy: the merge is a
  # union, so a smaller result means parse/merge corruption. Refuse to
  # install or push it.
  merged_count="$(grep -c '^- cmd: ' "$merged_file" || true)"
  remote_count="$(grep -c '^- cmd: ' "$temp_file" || true)"
  if [ "${merged_count:-0}" -lt "${remote_count:-0}" ]; then
    echo "Merged history ($merged_count entries) is smaller than remote ($remote_count); aborting to avoid data loss"
    exit 1
  fi

  # Snapshot the current local history before replacing it.
  if [ -s "$history_file" ]; then
    cp -p "$history_file" "$history_file.bak"
  fi
  mv "$merged_file" "$history_file"
  chmod 600 "$history_file" # history may hold secrets; match fish's own perms
  echo "History merged successfully (backup: $history_file.bak)"
else
  # The pull failed. Distinguish "no remote item yet" (first run) from a
  # transient/auth/network error: in the latter case the item exists, so
  # pushing now would overwrite a good remote copy with local-only history.
  if op item get "$item_name" > /dev/null 2>&1; then
    echo "Failed to fetch existing remote history; aborting to avoid overwriting remote" >&2
    [ -s "$op_err" ] && cat "$op_err" >&2
    exit 1
  fi
  echo "No remote history found, will create new sync item"
fi

# Push updated history back to 1Password
if op document edit "$item_name" "$history_file" 2> /dev/null; then
  echo "History synced to 1Password"
elif op document create "$history_file" --title "$item_name" > /dev/null 2>&1; then
  echo "Created new history sync item in 1Password"
else
  echo "Failed to sync history to 1Password"
  exit 1
fi

echo "Fish history sync completed"
