set -l __ai_harnesses cursor claude codex gemini opencode pi copilot
set -l __ai_aliases audit offline
set -l __ai_depths fast balanced deep
set -l __ai_executions readonly supervised autonomous
set -l __ai_connectivities online offline

complete -c ',ai' -f
complete -c ',ai' -n "not __fish_seen_subcommand_from $__ai_harnesses" -a "$__ai_harnesses" -d 'AI harness'
complete -c ',ai' -l alias -x -a "$__ai_aliases" -d 'Expand a named axis alias'
complete -c ',ai' -l depth -x -a "$__ai_depths" -d 'Soft reasoning-depth preference'
complete -c ',ai' -l execution -x -a "$__ai_executions" -d 'Hard execution constraint when explicit'
complete -c ',ai' -l connectivity -x -a "$__ai_connectivities" -d 'Hard connectivity constraint when explicit'
complete -c ',ai' -l model -r -d 'Explicit harness model'
complete -c ',ai' -l provider -r -d 'Explicit provider when the harness supports it'
complete -c ',ai' -l dry-run -d 'Emit redacted InvocationPlan JSON without executing'
complete -c ',ai' -l explain -d 'Explain the redacted InvocationPlan without executing'
complete -c ',ai' -s h -l help -d 'Show help'
