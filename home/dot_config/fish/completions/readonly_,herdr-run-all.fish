if not functions -q __comma_is_completing_option
    function __comma_is_completing_option
        set -l cur (commandline -ct 2>/dev/null)
        test -n "$cur"; and string match -qr '^-+' -- $cur
    end
end

function __f_herdr_run_all_workspaces
    if __comma_is_completing_option
        return
    end
    if command -v herdr >/dev/null 2>&1
        herdr workspace list 2>/dev/null | jq -r '.result.workspaces[].label' 2>/dev/null
    end
end

complete -c ,herdr-run-all -l all -d "Run in every idle pane (default: first idle pane per workspace)"
complete -c ,herdr-run-all -n '__fish_is_first_token; and not __comma_is_completing_option' -f -a "(__f_herdr_run_all_workspaces)" -d "Workspace pattern"
complete -c ,herdr-run-all -n "__fish_seen_subcommand_from (__f_herdr_run_all_workspaces); and not __comma_is_completing_option" -f -a "(__f_herdr_run_all_workspaces)" -d "Exclude pattern"

complete -c ,herdr-run-all -s h -l help -d "Show help message"
