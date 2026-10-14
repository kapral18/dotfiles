set -l __task_subcommands card check block reopen status scope correct pref steering hook

function __task_items
    ,task card show 2>/dev/null | string replace -rf '^- \[.\] (D\d+): (.*)$' '$1\t$2'
end

complete -c ,task -f
complete -c ,task -s h -l help -d 'Show help'
complete -c ,task -n "not __fish_seen_subcommand_from $__task_subcommands" -a card -d 'Write, show, or clear the intent card'
complete -c ,task -n "not __fish_seen_subcommand_from $__task_subcommands" -a check -d 'Mark a Done-when item met'
complete -c ,task -n "not __fish_seen_subcommand_from $__task_subcommands" -a block -d 'Mark a Done-when item blocked'
complete -c ,task -n "not __fish_seen_subcommand_from $__task_subcommands" -a reopen -d 'Mark a Done-when item open again'
complete -c ,task -n "not __fish_seen_subcommand_from $__task_subcommands" -a status -d 'List open Done-when items'
complete -c ,task -n "not __fish_seen_subcommand_from $__task_subcommands" -a scope -d 'Extend or check the card scope'
complete -c ,task -n "not __fish_seen_subcommand_from $__task_subcommands" -a correct -d 'Record a user correction'
complete -c ,task -n "not __fish_seen_subcommand_from $__task_subcommands" -a pref -d 'Lasting user preferences'
complete -c ,task -n "not __fish_seen_subcommand_from $__task_subcommands" -a steering -d 'Report logged corrections'
complete -c ,task -n "not __fish_seen_subcommand_from $__task_subcommands" -a hook -d 'Harness adapter entry point'
complete -c ,task -n '__fish_seen_subcommand_from card; and not __fish_seen_subcommand_from set show clear' -a 'set show clear'
complete -c ,task -n '__fish_seen_subcommand_from card; and __fish_seen_subcommand_from set show clear' -l session -x -d 'Harness session id'
complete -c ,task -n '__fish_seen_subcommand_from card; and __fish_seen_subcommand_from show' -l json -d 'Print the stored JSON'
complete -c ,task -n '__fish_seen_subcommand_from check block reopen' -a '(__task_items)'
complete -c ,task -n '__fish_seen_subcommand_from check' -l evidence -x -d 'Command and result'
complete -c ,task -n '__fish_seen_subcommand_from block' -l reason -x -d 'What blocks it'
complete -c ,task -n '__fish_seen_subcommand_from scope; and not __fish_seen_subcommand_from add check' -a 'add check'
complete -c ,task -n '__fish_seen_subcommand_from scope; and __fish_seen_subcommand_from add check' -F
complete -c ,task -n '__fish_seen_subcommand_from scope; and __fish_seen_subcommand_from add' -l reason -x -d 'Why the goal needs it'
complete -c ,task -n '__fish_seen_subcommand_from correct' -l harness -x -d 'Harness name'
complete -c ,task -n '__fish_seen_subcommand_from pref; and not __fish_seen_subcommand_from add list' -a 'add list'
complete -c ,task -n '__fish_seen_subcommand_from pref; and __fish_seen_subcommand_from add' -l global -d 'Apply in every repo'
complete -c ,task -n '__fish_seen_subcommand_from steering' -l days -x -d 'Days to report'
complete -c ,task -n '__fish_seen_subcommand_from steering' -l recent -x -d 'Recent entries to print'
complete -c ,task -n '__fish_seen_subcommand_from hook; and not __fish_seen_subcommand_from prompt tool compact stop codex' -a 'prompt tool compact stop codex'
complete -c ,task -n '__fish_seen_subcommand_from hook' -l harness -x -d 'Harness name'
complete -c ,task -n '__fish_seen_subcommand_from hook' -l input -x -d 'JSON input'
complete -c ,task -n '__fish_seen_subcommand_from check block reopen status scope correct' -l session -x -d 'Harness session id'
