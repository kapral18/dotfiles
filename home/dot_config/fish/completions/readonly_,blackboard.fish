set -l __blackboard_subcommands signal add waive state query gate survival boards
set -l __blackboard_priorities critical high medium low
set -l __blackboard_types observation analysis calculation strategy gap contradiction
set -l __blackboard_statuses active disputed superseded

complete -c ',blackboard' -f
complete -c ',blackboard' -s h -l help -d 'Show help'

complete -c ',blackboard' -n "not __fish_seen_subcommand_from $__blackboard_subcommands" -a signal -d 'Open a blocking question'
complete -c ',blackboard' -n "not __fish_seen_subcommand_from $__blackboard_subcommands" -a add -d 'Add a typed finding'
complete -c ',blackboard' -n "not __fish_seen_subcommand_from $__blackboard_subcommands" -a waive -d 'Waive a signal'
complete -c ',blackboard' -n "not __fish_seen_subcommand_from $__blackboard_subcommands" -a state -d 'Show board state'
complete -c ',blackboard' -n "not __fish_seen_subcommand_from $__blackboard_subcommands" -a query -d 'Filter entries'
complete -c ',blackboard' -n "not __fish_seen_subcommand_from $__blackboard_subcommands" -a gate -d 'Check synthesis gate'
complete -c ',blackboard' -n "not __fish_seen_subcommand_from $__blackboard_subcommands" -a survival -d 'Check final artifact survival'
complete -c ',blackboard' -n "not __fish_seen_subcommand_from $__blackboard_subcommands" -a boards -d 'List boards'

complete -c ',blackboard' -n '__fish_seen_subcommand_from signal add waive state query gate survival' -l board -r -d 'Board name'
complete -c ',blackboard' -n '__fish_seen_subcommand_from signal add' -l content -r -d 'Entry content'
complete -c ',blackboard' -n '__fish_seen_subcommand_from signal' -l priority -x -a "$__blackboard_priorities" -d 'Signal priority'
complete -c ',blackboard' -n '__fish_seen_subcommand_from signal add' -l by -r -d 'Worker or agent label'
complete -c ',blackboard' -n '__fish_seen_subcommand_from add query' -l type -x -a "$__blackboard_types" -d 'Entry type'
complete -c ',blackboard' -n '__fish_seen_subcommand_from add' -l source-doc -r -d 'Document or URL'
complete -c ',blackboard' -n '__fish_seen_subcommand_from add' -l source-ref -r -d 'Section or path:line'
complete -c ',blackboard' -n '__fish_seen_subcommand_from add' -l evidence -r -d 'Supporting quote'
complete -c ',blackboard' -n '__fish_seen_subcommand_from add' -l confidence -r -d 'Confidence 0..1'
complete -c ',blackboard' -n '__fish_seen_subcommand_from add' -l addresses -r -d 'Signal ids'
complete -c ',blackboard' -n '__fish_seen_subcommand_from add' -l supports -r -d 'Supported entry ids'
complete -c ',blackboard' -n '__fish_seen_subcommand_from add' -l contradicts -r -d 'Contradicted entry ids'
complete -c ',blackboard' -n '__fish_seen_subcommand_from add' -l supersedes -r -d 'Superseded entry ids'
complete -c ',blackboard' -n '__fish_seen_subcommand_from add' -l must-surface -d 'Require final artifact coverage'
complete -c ',blackboard' -n '__fish_seen_subcommand_from waive query' -l signal -r -d 'Signal id'
complete -c ',blackboard' -n '__fish_seen_subcommand_from waive' -l reason -r -d 'Waiver reason'
complete -c ',blackboard' -n '__fish_seen_subcommand_from state query gate survival boards' -l json -d 'Emit JSON'
complete -c ',blackboard' -n '__fish_seen_subcommand_from query' -l status -x -a "$__blackboard_statuses" -d 'Entry status'
complete -c ',blackboard' -n '__fish_seen_subcommand_from query' -l grep -r -d 'Substring filter'
complete -c ',blackboard' -n '__fish_seen_subcommand_from query' -l limit -r -d 'Maximum rows'
complete -c ',blackboard' -n '__fish_seen_subcommand_from survival' -l report -r -a '(__fish_complete_path)' -d 'Final artifact path'
