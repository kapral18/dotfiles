function __comma_sem_seen_subcommand
    __fish_seen_subcommand_from diff impact blame graph log help
end

complete -c ',sem' -s h -l help -d "Print help"
complete -c ',sem' -n 'not __comma_sem_seen_subcommand' -s V -l version -d "Print version"

complete -c ',sem' -n 'not __comma_sem_seen_subcommand' -f -a diff -d "Show semantic diff of changes"
complete -c ',sem' -n 'not __comma_sem_seen_subcommand' -f -a impact -d "Show impact of changing an entity"
complete -c ',sem' -n 'not __comma_sem_seen_subcommand' -f -a blame -d "Show semantic blame for a file"
complete -c ',sem' -n 'not __comma_sem_seen_subcommand' -f -a graph -d "Show entity dependency graph"
complete -c ',sem' -n 'not __comma_sem_seen_subcommand' -f -a log -d "Show evolution of an entity through git history"
complete -c ',sem' -n 'not __comma_sem_seen_subcommand' -f -a help -d "Print help for a command"
complete -c ',sem' -n '__fish_seen_subcommand_from help' -f -a diff -d "Help for semantic diff"
complete -c ',sem' -n '__fish_seen_subcommand_from help' -f -a impact -d "Help for impact analysis"
complete -c ',sem' -n '__fish_seen_subcommand_from help' -f -a blame -d "Help for semantic blame"
complete -c ',sem' -n '__fish_seen_subcommand_from help' -f -a graph -d "Help for dependency graph"
complete -c ',sem' -n '__fish_seen_subcommand_from help' -f -a log -d "Help for entity history"

complete -c ',sem' -n '__fish_seen_subcommand_from diff' -l staged -d "Show only staged changes"
complete -c ',sem' -n '__fish_seen_subcommand_from diff' -l cached -d "Show only staged changes"
complete -c ',sem' -n '__fish_seen_subcommand_from diff' -l commit -d "Show changes from a specific commit" -x
complete -c ',sem' -n '__fish_seen_subcommand_from diff' -l from -d "Start of commit range" -x
complete -c ',sem' -n '__fish_seen_subcommand_from diff' -l to -d "End of commit range" -x
complete -c ',sem' -n '__fish_seen_subcommand_from diff' -l stdin -d "Read FileChange[] JSON from stdin"
complete -c ',sem' -n '__fish_seen_subcommand_from diff' -l format -d "Set output format" -x -a "terminal json markdown"
complete -c ',sem' -n '__fish_seen_subcommand_from diff' -s v -l verbose -d "Show inline content diffs for each entity"
complete -c ',sem' -n '__fish_seen_subcommand_from diff' -l file-exts -d "Only include files with these extensions" -x

complete -c ',sem' -n '__fish_seen_subcommand_from impact' -l files -d "Specific files to analyze" -r
complete -c ',sem' -n '__fish_seen_subcommand_from impact' -l json -d "Output as JSON"
complete -c ',sem' -n '__fish_seen_subcommand_from impact' -l file-exts -d "Only include files with these extensions" -x

complete -c ',sem' -n '__fish_seen_subcommand_from blame' -l json -d "Output as JSON"

complete -c ',sem' -n '__fish_seen_subcommand_from graph' -l entity -d "Show dependencies or dependents for an entity" -x
complete -c ',sem' -n '__fish_seen_subcommand_from graph' -l format -d "Set output format" -x -a "terminal json markdown"
complete -c ',sem' -n '__fish_seen_subcommand_from graph' -l file-exts -d "Only include files with these extensions" -x

complete -c ',sem' -n '__fish_seen_subcommand_from log' -l file -d "File containing the entity" -r
complete -c ',sem' -n '__fish_seen_subcommand_from log' -l limit -d "Maximum number of commits to scan" -x
complete -c ',sem' -n '__fish_seen_subcommand_from log' -l json -d "Output as JSON"
complete -c ',sem' -n '__fish_seen_subcommand_from log' -s v -l verbose -d "Show content diff between versions"
