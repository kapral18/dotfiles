set -l __task_subcommands card review check block reopen status scope correct pref steering guards guard board handoff hook claim stance finding

function __task_command_at
    set -l position $argv[1]
    set -l words (commandline -xpc)
    set -q words[$position]
    and contains -- $words[$position] $argv[2..-1]
end

function __task_items
    argparse --ignore-unknown 'session=' -- (commandline -xpc) 2>/dev/null
    or return
    set -l session_args
    if set -q _flag_session
        set session_args --session "$_flag_session"
    end
    ,task card show $session_args 2>/dev/null | string replace -rf '^- \[.\] (D\d+): (.*)$' '$1\t$2'
end

function __task_handoff_topics
    argparse --ignore-unknown 'repo=' -- (commandline -xpc) 2>/dev/null
    or return
    set -l repo_args
    if set -q _flag_repo
        set repo_args --repo "$_flag_repo"
    end
    ,task handoff list $repo_args 2>/dev/null | string replace -rf '^\S+ \S+  (\S+)$' '$1'
end

complete -c ,task -f
complete -c ,task -s h -l help -d 'Show help'
complete -c ,task -n "not __task_command_at 2 $__task_subcommands" -a card -d 'Write, show, or clear the intent card'
complete -c ,task -n "not __task_command_at 2 $__task_subcommands" -a review -d 'Checkpoint review acceptance and print its history'
complete -c ,task -n '__task_command_at 2 review' -l reason -x -d 'User change or evidence justifying revised acceptance'
complete -c ,task -n "not __task_command_at 2 $__task_subcommands" -a check -d 'Mark a Done-when item met'
complete -c ,task -n "not __task_command_at 2 $__task_subcommands" -a block -d 'Mark a Done-when item blocked'
complete -c ,task -n "not __task_command_at 2 $__task_subcommands" -a reopen -d 'Mark a Done-when item open again'
complete -c ,task -n "not __task_command_at 2 $__task_subcommands" -a status -d 'List open Done-when items'
complete -c ,task -n "not __task_command_at 2 $__task_subcommands" -a scope -d 'Extend or check the card scope'
complete -c ,task -n "not __task_command_at 2 $__task_subcommands" -a correct -d 'Record a user correction'
complete -c ,task -n "not __task_command_at 2 $__task_subcommands" -a pref -d 'Lasting user preferences'
complete -c ,task -n "not __task_command_at 2 $__task_subcommands" -a steering -d 'Report logged corrections'
complete -c ,task -n "not __task_command_at 2 $__task_subcommands" -a guards -d "Report each guard's fires and outcomes"
complete -c ,task -n "not __task_command_at 2 $__task_subcommands" -a guard -d 'Log a guard fire from a harness mod'
complete -c ,task -n "not __task_command_at 2 $__task_subcommands" -a board -d 'List sessions by what they wait on'
complete -c ,task -n "not __task_command_at 2 $__task_subcommands" -a handoff -d 'Save and resume a task across sessions'
complete -c ,task -n "not __task_command_at 2 $__task_subcommands" -a hook -d 'Harness adapter entry point'
complete -c ,task -n '__task_command_at 2 card; and not __task_command_at 3 set show clear' -a 'set show clear'
complete -c ,task -n '__task_command_at 2 card; and __task_command_at 3 set show clear' -l session -x -d 'Harness session id'
complete -c ,task -n '__task_command_at 2 card; and __task_command_at 3 show' -l json -d 'Print the stored JSON'
complete -c ,task -n '__task_command_at 2 check block reopen' -a '(__task_items)'
complete -c ,task -n '__task_command_at 2 check' -l claim -x -d 'Verified claim ID'
complete -c ,task -n '__task_command_at 2 block' -l reason -x -d 'What blocks it'
complete -c ,task -n '__task_command_at 2 scope; and not __task_command_at 3 add check' -a 'add check'
complete -c ,task -n '__task_command_at 2 scope; and __task_command_at 3 add check' -F
complete -c ,task -n '__task_command_at 2 scope; and __task_command_at 3 add' -l reason -x -d "Why the goal or a defect in the change's impact needs it"
complete -c ,task -n '__task_command_at 2 correct' -l harness -x -d 'Harness name'
complete -c ,task -n '__task_command_at 2 pref; and not __task_command_at 3 add list' -a 'add list'
complete -c ,task -n '__task_command_at 2 pref; and __task_command_at 3 add' -l global -d 'Apply in every repo'
complete -c ,task -n '__task_command_at 2 steering' -l days -x -d 'Days to report'
complete -c ,task -n '__task_command_at 2 steering' -l recent -x -d 'Recent entries to print'
complete -c ,task -n '__task_command_at 2 hook; and not __task_command_at 3 prompt tool compact stop evidence checkpoint user codex sentback' -a 'prompt tool compact stop evidence checkpoint user codex sentback'
complete -c ,task -n '__task_command_at 2 hook' -l harness -x -d 'Harness name'
complete -c ,task -n '__task_command_at 2 hook' -l input -x -d 'JSON input'
complete -c ,task -n '__task_command_at 2 hook' -l input-file -r -d 'File holding JSON input'
complete -c ,task -n '__task_command_at 2 review check block reopen status scope correct' -l session -x -d 'Harness session id'

complete -c ,task -n "not __task_command_at 2 $__task_subcommands" -a claim -d 'Record a factual claim and source'
complete -c ,task -n "not __task_command_at 2 $__task_subcommands" -a stance -d 'Record a decision and its reason'
complete -c ,task -n "not __task_command_at 2 $__task_subcommands" -a finding -d 'Resolve a review finding'
complete -c ,task -n '__task_command_at 2 claim; and not __task_command_at 3 add' -a add
complete -c ,task -n '__task_command_at 2 stance; and not __task_command_at 3 set' -a set
complete -c ,task -n '__task_command_at 2 finding; and not __task_command_at 3 resolve' -a resolve
complete -c ,task -n '__task_command_at 2 claim' -l quote -x -d 'Exact Claude tool output'
complete -c ,task -n '__task_command_at 2 claim' -l file -r -d 'Source path:line'
complete -c ,task -n '__task_command_at 2 claim' -l text -x -d 'Exact source line'
complete -c ,task -n '__task_command_at 2 claim' -l unknown -x -d 'Why verification is unavailable'
complete -c ,task -n '__task_command_at 2 stance' -l because -x -d 'Verified claim ID'
complete -c ,task -n '__task_command_at 2 stance' -l user -x -d 'Verbatim user words'
complete -c ,task -n '__task_command_at 2 finding' -l fixed -x -d 'Claim proving the fix'
complete -c ,task -n '__task_command_at 2 finding' -l rejected -x -d 'Claim refuting the finding'
complete -c ,task -n '__task_command_at 2 claim stance finding' -l session -x -d 'Harness session id'

complete -c ,task -n '__task_command_at 2 guards' -l days -x -d 'Days to report'
complete -c ,task -n '__task_command_at 2 guards' -l recent -x -d 'Fires to list for one guard'
complete -c ,task -n '__task_command_at 2 guard; and not __task_command_at 3 log' -a log
complete -c ,task -n '__task_command_at 2 guard; and __task_command_at 3 log' -l detail -x -d 'What the guard fired on'
complete -c ,task -n '__task_command_at 2 guard; and __task_command_at 3 log' -l harness -x -d 'Harness name'
complete -c ,task -n '__task_command_at 2 guard; and __task_command_at 3 log' -l session -x -d 'Harness session id'
complete -c ,task -n '__task_command_at 2 handoff; and not __task_command_at 3 save show resume list' -a 'save show resume list'
complete -c ,task -n '__task_command_at 2 handoff; and __task_command_at 3 show resume' -a '(__task_handoff_topics)'
complete -c ,task -n '__task_command_at 2 handoff' -l repo -x -d 'Repo namespace'
complete -c ,task -n '__task_command_at 2 handoff; and __task_command_at 3 show' -l prev -d 'Print the previous version'
complete -c ,task -n '__task_command_at 2 handoff; and __task_command_at 3 save resume' -l session -x -d 'Harness session id'
complete -c ,task -n '__task_command_at 2 handoff; and __task_command_at 3 list' -l all -d 'List notes across every repo'
