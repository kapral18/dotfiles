function __f_tmux_run_all_tmux_sessions
    if command -v tmux >/dev/null 2>&1
        tmux list-sessions -F '#{session_name}' 2>/dev/null
    end
end

complete -c f-tmux-run-all -n __fish_is_first_token -f -a "(__f_tmux_run_all_tmux_sessions)" -d "Session pattern"
complete -c f-tmux-run-all -n "__fish_seen_subcommand_from (__f_tmux_run_all_tmux_sessions)" -f -a "(__f_tmux_run_all_tmux_sessions)" -d "Exclude pattern"

complete -c f-tmux-run-all -s h -l help -d "Show help message"

