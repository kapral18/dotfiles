set -l __handoff_subcommands save show list

function __handoff_topics
    ,handoff list 2>/dev/null | string replace -r '^\S+ \S+\s+' ''
end

complete -c ,handoff -f
complete -c ,handoff -l repo -x -d 'Repo namespace (default: current git repo, else global)'
complete -c ,handoff -s h -l help -d 'Show help'
complete -c ,handoff -n "not __fish_seen_subcommand_from $__handoff_subcommands" -a save -d 'Save the note on stdin as <topic>'
complete -c ,handoff -n "not __fish_seen_subcommand_from $__handoff_subcommands" -a show -d 'Print the note for <topic>'
complete -c ,handoff -n "not __fish_seen_subcommand_from $__handoff_subcommands" -a list -d 'List notes, newest first'
complete -c ,handoff -n '__fish_seen_subcommand_from save show' -a '(__handoff_topics)' -d Topic
complete -c ,handoff -n '__fish_seen_subcommand_from show' -l prev -d 'Print the previous version'
complete -c ,handoff -n '__fish_seen_subcommand_from list' -l all -d 'List notes across every repo'
