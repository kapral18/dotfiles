# Completions for ,agent-memory.

function __agent_memory_topics
    set -l workspace (pwd -P)
    set -l spec_dir /tmp/specs/(string trim -l -c / -- $workspace)
    test -d "$spec_dir"; or return

    for file in "$spec_dir"/*
        test -e "$file"; or continue
        set -l base (basename "$file")
        switch "$base"
            case _active_topic.txt
                continue
            case '*.worklog.jsonl'
                string replace -r '\.worklog\.jsonl$' '' -- "$base"
            case '*.no_context'
                string replace -r '\.no_context$' '' -- "$base"
            case '*.txt'
                string replace -r '\.txt$' '' -- "$base"
        end
    end | sort -u
end

set -l __agent_memory_subcommands status select use merge note wipe-current

complete -c ',agent-memory' -f

complete -c ',agent-memory' -n "not __fish_seen_subcommand_from $__agent_memory_subcommands" \
    -a status -d 'Show selected hook memory topic'
complete -c ',agent-memory' -n "not __fish_seen_subcommand_from $__agent_memory_subcommands" \
    -a select -d 'Bind this agent session to a topic bucket'
complete -c ',agent-memory' -n "not __fish_seen_subcommand_from $__agent_memory_subcommands" \
    -a use -d 'Set the active named topic'
complete -c ',agent-memory' -n "not __fish_seen_subcommand_from $__agent_memory_subcommands" \
    -a merge -d 'Merge a duplicate topic into a destination topic'
complete -c ',agent-memory' -n "not __fish_seen_subcommand_from $__agent_memory_subcommands" \
    -a note -d 'Record a structured insight into the topic worklog'
complete -c ',agent-memory' -n "not __fish_seen_subcommand_from $__agent_memory_subcommands" \
    -a wipe-current -d 'Delete selected hook memory topic files'

complete -c ',agent-memory' -l workspace -r -d 'Workspace path'
complete -c ',agent-memory' -n "__fish_seen_subcommand_from status select note wipe-current" \
    -l session-id -r -d 'Agent runtime session id'
complete -c ',agent-memory' -n "__fish_seen_subcommand_from status note wipe-current" \
    -l topic -x -a '(__agent_memory_topics)' -d 'Override selected topic'
complete -c ',agent-memory' -n '__fish_seen_subcommand_from select' \
    -x -a '(__agent_memory_topics)' -d 'Topic bucket to bind this session to'
complete -c ',agent-memory' -n '__fish_seen_subcommand_from select' \
    -l create -d 'Seed the topic bucket if missing'
complete -c ',agent-memory' -n '__fish_seen_subcommand_from use' \
    -x -a '(__agent_memory_topics)' -d 'Named topic to activate'
complete -c ',agent-memory' -n '__fish_seen_subcommand_from merge' \
    -x -a '(__agent_memory_topics)' -d 'Source or destination topic'
complete -c ',agent-memory' -n '__fish_seen_subcommand_from note; and not __fish_seen_subcommand_from fact gotcha pattern anti_pattern recipe principle question decision' \
    -x -a 'fact gotcha pattern anti_pattern recipe principle question decision' -d 'Structured note kind (capsule taxonomy + question/decision)'
complete -c ',agent-memory' -n '__fish_seen_subcommand_from note' \
    -l ref -r -d 'Evidence anchor (path:line, command, or URL; repeatable)'

complete -c ',agent-memory' -n "__fish_seen_subcommand_from merge wipe-current" \
    -l dry-run -d 'Print plan without changing files'
complete -c ',agent-memory' -n '__fish_seen_subcommand_from wipe-current' \
    -l reset-active -d 'Also remove _active_topic.txt'
