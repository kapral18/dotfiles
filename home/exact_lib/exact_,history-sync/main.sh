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

if ! command -v op &> /dev/null; then
  echo "1Password CLI not found. Install with: brew install 1password-cli"
  exit 1
fi

if ! op account get > /dev/null 2>&1; then
  echo "1Password CLI not authenticated. Run: op signin"
  exit 1
fi

# Remote state is "present" or "absent" only when op lists the vault; a listing
# failure aborts so local-only history never overwrites an unreachable remote.
if ! remote_state="$(op item list --categories Document --format json 2> "$op_err" | python3 -c '
import json, sys
print("present" if any(item.get("title") == sys.argv[1] for item in json.loads(sys.stdin.read() or "[]")) else "absent")
' "$item_name" 2> /dev/null)"; then
  echo "Failed to query 1Password for remote history; aborting to avoid overwriting remote" >&2
  [ -s "$op_err" ] && cat "$op_err" >&2
  exit 1
fi

case "$remote_state" in
  present)
    if ! op document get "$item_name" --out-file "$temp_file" 2> "$op_err"; then
      echo "Failed to fetch existing remote history; aborting to avoid overwriting remote" >&2
      [ -s "$op_err" ] && cat "$op_err" >&2
      exit 1
    fi
    if [ ! -s "$temp_file" ] || ! grep -q "^- cmd:" "$temp_file"; then
      echo "Remote history appears corrupted, skipping sync"
      exit 1
    fi

    merge_script="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/fish-history-merge.py"
    local_snapshot="$tmp_dir/local"
    # Merge from a snapshot, and merge again if fish appended while the merge ran.
    for _attempt in 1 2 3; do
      if [ -f "$history_file" ]; then cp -p "$history_file" "$local_snapshot"; else : > "$local_snapshot"; fi
      if ! python3 "$merge_script" "$local_snapshot" "$temp_file" "$merged_file" || [ ! -s "$merged_file" ]; then
        echo "Failed to merge histories"
        exit 1
      fi
      if [ ! -f "$history_file" ] || cmp -s "$history_file" "$local_snapshot"; then
        break
      fi
    done
    if [ -f "$history_file" ] && ! cmp -s "$history_file" "$local_snapshot"; then
      echo "Fish history kept changing during the merge; run the sync again" >&2
      exit 1
    fi

    # The merge is a union of unique commands, so it never holds fewer than
    # either side; fewer means parse/merge corruption. Refuse to install or push it.
    unique_cmds() { { grep '^- cmd: ' "$1" 2> /dev/null || true; } | sort -u | wc -l | tr -d ' '; }
    merged_count="$(unique_cmds "$merged_file")"
    for side in remote:"$temp_file" local:"$local_snapshot"; do
      side_count="$(unique_cmds "${side#*:}")"
      if [ "$merged_count" -lt "$side_count" ]; then
        echo "Merged history ($merged_count commands) is smaller than ${side%%:*} ($side_count); aborting to avoid data loss"
        exit 1
      fi
    done

    backup=""
    if [ -s "$history_file" ]; then
      backup="$history_file.bak.$(date +%Y%m%d%H%M%S)"
      cp -p "$history_file" "$backup"
      # Keep the three newest backups.
      ls -1t "$history_file".bak.* 2> /dev/null | tail -n +4 | while IFS= read -r old; do rm -f "$old"; done
      rm -f "$history_file.bak" # the old fixed-name backup
    fi
    if [ -f "$history_file" ] && ! cmp -s "$history_file" "$local_snapshot"; then
      echo "Fish history changed during the sync; run it again" >&2
      exit 1
    fi
    mv "$merged_file" "$history_file"
    chmod 600 "$history_file" # history may hold secrets; match fish's own perms
    echo "History merged successfully${backup:+ (backup: $backup)}"
    if ! op document edit "$item_name" "$history_file" 2> "$op_err"; then
      echo "Failed to sync history to 1Password" >&2
      [ -s "$op_err" ] && cat "$op_err" >&2
      exit 1
    fi
    echo "History synced to 1Password"
    ;;
  absent)
    echo "No remote history found, will create new sync item"
    if ! op document create "$history_file" --title "$item_name" > /dev/null 2> "$op_err"; then
      echo "Failed to sync history to 1Password" >&2
      [ -s "$op_err" ] && cat "$op_err" >&2
      exit 1
    fi
    echo "Created new history sync item in 1Password"
    ;;
esac

echo "Fish history sync completed"
