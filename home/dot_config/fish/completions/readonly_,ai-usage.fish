complete -c ',ai-usage' -f
complete -c ',ai-usage' -l days -d 'Look back this many days (default 7)' -r
complete -c ',ai-usage' -l harness -d 'Restrict to a harness (repeatable)' -r -a 'claude codex copilot omp opencode pi'
complete -c ',ai-usage' -l by -d 'Group rows' -r -a 'session harness model'
complete -c ',ai-usage' -l limit -d 'Rows to print (default 40)' -r
complete -c ',ai-usage' -l json -d 'Emit JSON instead of a table'
complete -c ',ai-usage' -l signals -d 'Show prompts, user-correction signals and SOP re-injections per row'
complete -c ',ai-usage' -s h -l help -d 'Show help'
