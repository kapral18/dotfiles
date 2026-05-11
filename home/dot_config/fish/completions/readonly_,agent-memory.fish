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
            case '*.evidence_state.json'
                string replace -r '\.evidence_state\.json$' '' -- "$base"
            case '*.evidence_decisions.jsonl'
                string replace -r '\.evidence_decisions\.jsonl$' '' -- "$base"
            case '*.no_context'
                string replace -r '\.no_context$' '' -- "$base"
            case '*.txt'
                string replace -r '\.txt$' '' -- "$base"
        end
    end | sort -u
end

set -l __agent_memory_subcommands status wipe-current

complete -c ',agent-memory' -f

complete -c ',agent-memory' -n "not __fish_seen_subcommand_from $__agent_memory_subcommands" \
    -a status -d 'Show selected hook memory topic'
complete -c ',agent-memory' -n "not __fish_seen_subcommand_from $__agent_memory_subcommands" \
    -a wipe-current -d 'Delete selected hook memory topic files'

complete -c ',agent-memory' -l workspace -r -d 'Workspace path'
complete -c ',agent-memory' -l topic -x -a '(__agent_memory_topics)' -d 'Override selected topic'

complete -c ',agent-memory' -n '__fish_seen_subcommand_from wipe-current' \
    -l dry-run -d 'Print files without deleting'
complete -c ',agent-memory' -n '__fish_seen_subcommand_from wipe-current' \
    -l reset-active -d 'Also remove _active_topic.txt'
