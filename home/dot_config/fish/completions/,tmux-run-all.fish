function __f_tmux_run_all_tmux_sessions
    if command -v tmux >/dev/null 2>&1
        tmux list-sessions -F '#{session_name}' 2>/dev/null
    end
end

complete -c ,tmux-run-all -l all -d "Run command in all idle panes (default: first idle pane of first window)"
complete -c ,tmux-run-all -n __fish_is_first_token -f -a "(__f_tmux_run_all_tmux_sessions)" -d "Session pattern"
complete -c ,tmux-run-all -n "__fish_seen_subcommand_from (__f_tmux_run_all_tmux_sessions)" -f -a "(__f_tmux_run_all_tmux_sessions)" -d "Exclude pattern"

complete -c ,tmux-run-all -s h -l help -d "Show help message"
