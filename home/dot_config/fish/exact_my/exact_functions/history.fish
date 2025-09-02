function history-sync --description "Sync fish history via 1Password CLI (chronological)"
    set -l history_file "$HOME/.local/share/fish/fish_history"
    set -l item_name fish-history-sync
    set -l temp_file /tmp/fish_history_remote
    set -l merged_file /tmp/fish_history_merged

    # Check if op CLI is available and authenticated
    if not type -q op
        echo "1Password CLI not found. Install with: brew install 1password-cli"
        return 1
    end

    if not op account get >/dev/null 2>&1
        echo "1Password CLI not authenticated. Run: op signin"
        return 1
    end

    # Pull remote history from 1Password
    if op document get "$item_name" --out-file "$temp_file" 2>/dev/null
        # Verify remote file integrity
        if not test -s "$temp_file" || not grep -q "^- cmd:" "$temp_file"
            echo "Remote history appears corrupted, skipping sync"
            rm -f "$temp_file"
            return 1
        end

        # Merge histories using external Python script
        set -l merge_script "$HOME/.config/fish/my/functions/history/fish-history-merge.py"
        "$merge_script" "$history_file" "$temp_file" "$merged_file"

        if test $status -eq 0 && test -s "$merged_file"
            mv "$merged_file" "$history_file"
            echo "History merged successfully"
        else
            echo "Failed to merge histories"
            rm -f "$temp_file" "$merged_file"
            return 1
        end
    else
        echo "No remote history found, will create new sync item"
    end

    # Push updated history back to 1Password
    if op document edit "$item_name" "$history_file" 2>/dev/null
        echo "History synced to 1Password"
    else if op document create "$history_file" --title "$item_name" >/dev/null 2>&1
        echo "Created new history sync item in 1Password"
    else
        echo "Failed to sync history to 1Password"
        rm -f "$temp_file" "$merged_file"
        return 1
    end

    # Cleanup
    rm -f "$temp_file" "$merged_file"

    echo "Fish history sync completed"
end
