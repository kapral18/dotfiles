set -l __task_subcommands card check block reopen status scope correct pref steering hook claim stance finding

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
complete -c ,task -n '__fish_seen_subcommand_from check' -l claim -x -d 'Verified claim ID'
complete -c ,task -n '__fish_seen_subcommand_from block' -l reason -x -d 'What blocks it'
complete -c ,task -n '__fish_seen_subcommand_from scope; and not __fish_seen_subcommand_from add check' -a 'add check'
complete -c ,task -n '__fish_seen_subcommand_from scope; and __fish_seen_subcommand_from add check' -F
complete -c ,task -n '__fish_seen_subcommand_from scope; and __fish_seen_subcommand_from add' -l reason -x -d "Why the goal or a defect in the change's impact needs it"
complete -c ,task -n '__fish_seen_subcommand_from correct' -l harness -x -d 'Harness name'
complete -c ,task -n '__fish_seen_subcommand_from pref; and not __fish_seen_subcommand_from add list' -a 'add list'
complete -c ,task -n '__fish_seen_subcommand_from pref; and __fish_seen_subcommand_from add' -l global -d 'Apply in every repo'
complete -c ,task -n '__fish_seen_subcommand_from steering' -l days -x -d 'Days to report'
complete -c ,task -n '__fish_seen_subcommand_from steering' -l recent -x -d 'Recent entries to print'
complete -c ,task -n '__fish_seen_subcommand_from hook; and not __fish_seen_subcommand_from prompt tool compact stop evidence user codex' -a 'prompt tool compact stop evidence user codex'
complete -c ,task -n '__fish_seen_subcommand_from hook' -l harness -x -d 'Harness name'
complete -c ,task -n '__fish_seen_subcommand_from hook' -l input -x -d 'JSON input'
complete -c ,task -n '__fish_seen_subcommand_from check block reopen status scope correct' -l session -x -d 'Harness session id'

complete -c ,task -n "not __fish_seen_subcommand_from $__task_subcommands" -a claim -d 'Record a factual claim and source'
complete -c ,task -n "not __fish_seen_subcommand_from $__task_subcommands" -a stance -d 'Record a decision and its reason'
complete -c ,task -n "not __fish_seen_subcommand_from $__task_subcommands" -a finding -d 'Resolve a review finding'
complete -c ,task -n '__fish_seen_subcommand_from claim; and not __fish_seen_subcommand_from add' -a add
complete -c ,task -n '__fish_seen_subcommand_from stance; and not __fish_seen_subcommand_from set' -a set
complete -c ,task -n '__fish_seen_subcommand_from finding; and not __fish_seen_subcommand_from resolve' -a resolve
complete -c ,task -n '__fish_seen_subcommand_from claim' -l quote -x -d 'Exact Claude tool output'
complete -c ,task -n '__fish_seen_subcommand_from claim' -l file -r -d 'Source path:line'
complete -c ,task -n '__fish_seen_subcommand_from claim' -l text -x -d 'Exact source line'
complete -c ,task -n '__fish_seen_subcommand_from claim' -l unknown -x -d 'Why verification is unavailable'
complete -c ,task -n '__fish_seen_subcommand_from stance' -l because -x -d 'Verified claim ID'
complete -c ,task -n '__fish_seen_subcommand_from stance' -l user -x -d 'Verbatim user words'
complete -c ,task -n '__fish_seen_subcommand_from finding' -l fixed -x -d 'Claim proving the fix'
complete -c ,task -n '__fish_seen_subcommand_from finding' -l rejected -x -d 'Claim refuting the finding'
complete -c ,task -n '__fish_seen_subcommand_from claim stance finding' -l session -x -d 'Harness session id'
