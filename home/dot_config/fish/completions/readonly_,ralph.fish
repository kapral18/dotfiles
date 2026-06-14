set -l __ralph_subcommands dry-run go runner resume replan answer supervisor status runs role dashboard preview tail attach verify control kill rm statusline doctor
set -l __ralph_roles planner executor reviewer re_reviewer re-reviewer reflector
set -l __ralph_harnesses cursor pi command
set -l __ralph_control_actions takeover dirty resume auto
set -l __ralph_preview_modes summary tail

complete -c ',ralph' -f
complete -c ',ralph' -s h -l help -d 'Show help'
complete -c ',ralph' -l state-home -r -a '(__fish_complete_directories)' -d 'Override RALPH_STATE_HOME'
complete -c ',ralph' -l kb-home -r -a '(__fish_complete_directories)' -d 'Override AI_KB_HOME'

for subcommand in $__ralph_subcommands
    complete -c ',ralph' -n "not __fish_seen_subcommand_from $__ralph_subcommands" -a $subcommand
end

complete -c ',ralph' -n '__fish_seen_subcommand_from dry-run go' -l goal -r -d 'Free-text goal'
complete -c ',ralph' -n '__fish_seen_subcommand_from dry-run' -l memory-query -r -d 'KB recall query'
complete -c ',ralph' -n '__fish_seen_subcommand_from dry-run' -l memory-limit -r -d 'KB recall limit'
complete -c ',ralph' -n '__fish_seen_subcommand_from dry-run' -l acceptance -r -d 'Acceptance criteria'
complete -c ',ralph' -n '__fish_seen_subcommand_from go runs' -l workspace -r -a '(__fish_complete_directories)' -d 'Workspace path'
complete -c ',ralph' -n '__fish_seen_subcommand_from go' -l plan-only -d 'Plan and stop'
complete -c ',ralph' -n '__fish_seen_subcommand_from go' -l workflow -r -d 'Workflow hint'
complete -c ',ralph' -n '__fish_seen_subcommand_from go' -l roles-config -r -a '(__fish_complete_suffix .json)' -d 'Roles config path'
complete -c ',ralph' -n '__fish_seen_subcommand_from go' -l foreground -d 'Run inline'
complete -c ',ralph' -n '__fish_seen_subcommand_from go' -l detach -d 'Run detached'
complete -c ',ralph' -n '__fish_seen_subcommand_from go' -l subprocess -d 'Run roles as subprocesses'
complete -c ',ralph' -n '__fish_seen_subcommand_from go runner resume replan supervisor status runs role verify control kill' -l json -d 'Emit JSON'
complete -c ',ralph' -n '__fish_seen_subcommand_from go' -l planner-model -r -d 'Planner model override'
complete -c ',ralph' -n '__fish_seen_subcommand_from go' -l executor-model -r -d 'Executor model override'
complete -c ',ralph' -n '__fish_seen_subcommand_from go' -l reviewer-model -r -d 'Reviewer model override'
complete -c ',ralph' -n '__fish_seen_subcommand_from go' -l re-reviewer-model -r -d 'Re-reviewer model override'
complete -c ',ralph' -n '__fish_seen_subcommand_from go' -l planner-harness -x -a "$__ralph_harnesses" -d 'Planner harness override'
complete -c ',ralph' -n '__fish_seen_subcommand_from go' -l executor-harness -x -a "$__ralph_harnesses" -d 'Executor harness override'
complete -c ',ralph' -n '__fish_seen_subcommand_from go' -l reviewer-harness -x -a "$__ralph_harnesses" -d 'Reviewer harness override'
complete -c ',ralph' -n '__fish_seen_subcommand_from go' -l re-reviewer-harness -x -a "$__ralph_harnesses" -d 'Re-reviewer harness override'
complete -c ',ralph' -n '__fish_seen_subcommand_from go' -l planner-args -r -d 'Planner extra args'
complete -c ',ralph' -n '__fish_seen_subcommand_from go' -l executor-args -r -d 'Executor extra args'
complete -c ',ralph' -n '__fish_seen_subcommand_from go' -l reviewer-args -r -d 'Reviewer extra args'
complete -c ',ralph' -n '__fish_seen_subcommand_from go' -l re-reviewer-args -r -d 'Re-reviewer extra args'

complete -c ',ralph' -n '__fish_seen_subcommand_from resume' -l foreground -d 'Run inline'
complete -c ',ralph' -n '__fish_seen_subcommand_from replan answer' -l no-resume -d 'Do not auto-resume'
complete -c ',ralph' -n '__fish_seen_subcommand_from answer' -l question -r -d 'Question id'
complete -c ',ralph' -n '__fish_seen_subcommand_from answer' -l text -r -d 'Answer text'
complete -c ',ralph' -n '__fish_seen_subcommand_from answer' -l print-json -d 'Emit post-answer manifest'
complete -c ',ralph' -n '__fish_seen_subcommand_from answer' -l json -r -a '(__fish_complete_suffix .json)' -d 'Answers JSON path'
complete -c ',ralph' -n '__fish_seen_subcommand_from supervisor' -l loop -d 'Keep supervising'
complete -c ',ralph' -n '__fish_seen_subcommand_from supervisor' -l interval -r -d 'Loop interval seconds'
complete -c ',ralph' -n '__fish_seen_subcommand_from runs' -l limit -r -d 'Maximum runs'
complete -c ',ralph' -n '__fish_seen_subcommand_from runs' -l session -r -d 'Session id'
complete -c ',ralph' -n '__fish_seen_subcommand_from role preview tail attach control kill' -l role -x -a "$__ralph_roles" -d 'Role name'
complete -c ',ralph' -n '__fish_seen_subcommand_from preview' -l mode -x -a "$__ralph_preview_modes" -d 'Preview mode'
complete -c ',ralph' -n '__fish_seen_subcommand_from tail' -l lines -r -d 'Tail line count'
complete -c ',ralph' -n '__fish_seen_subcommand_from control' -l action -x -a "$__ralph_control_actions" -d 'Control action'
complete -c ',ralph' -n '__fish_seen_subcommand_from kill' -l all -d 'Kill every non-terminal run'
complete -c ',ralph' -n '__fish_seen_subcommand_from rm' -l all-completed -d 'Remove all completed runs'
complete -c ',ralph' -n '__fish_seen_subcommand_from rm' -l keep-learnings -d 'Keep learnings'
