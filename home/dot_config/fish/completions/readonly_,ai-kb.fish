set -l __ai_kb_subcommands init remember search get list reembed curate ingest harvest doctor
set -l __ai_kb_kinds fact gotcha pattern anti_pattern recipe principle doc
set -l __ai_kb_scopes workspace project domain universal
set -l __ai_kb_modes hybrid bm25 vector

complete -c ',ai-kb' -f

complete -c ',ai-kb' -l home -r -d 'Override AI_KB_HOME'
complete -c ',ai-kb' -s h -l help -d 'Show help'

complete -c ',ai-kb' -n "not __fish_seen_subcommand_from $__ai_kb_subcommands" -a init -d 'Initialize the knowledge base'
complete -c ',ai-kb' -n "not __fish_seen_subcommand_from $__ai_kb_subcommands" -a remember -d 'Store a capsule'
complete -c ',ai-kb' -n "not __fish_seen_subcommand_from $__ai_kb_subcommands" -a search -d 'Search capsules'
complete -c ',ai-kb' -n "not __fish_seen_subcommand_from $__ai_kb_subcommands" -a get -d 'Fetch one capsule'
complete -c ',ai-kb' -n "not __fish_seen_subcommand_from $__ai_kb_subcommands" -a list -d 'List recent capsules'
complete -c ',ai-kb' -n "not __fish_seen_subcommand_from $__ai_kb_subcommands" -a reembed -d 'Rebuild missing embeddings'
complete -c ',ai-kb' -n "not __fish_seen_subcommand_from $__ai_kb_subcommands" -a curate -d 'Run curation'
complete -c ',ai-kb' -n "not __fish_seen_subcommand_from $__ai_kb_subcommands" -a ingest -d 'Ingest markdown'
complete -c ',ai-kb' -n "not __fish_seen_subcommand_from $__ai_kb_subcommands" -a harvest -d 'Surface durable-memory candidates from a worklog'
complete -c ',ai-kb' -n "not __fish_seen_subcommand_from $__ai_kb_subcommands" -a doctor -d 'Check KB health'

complete -c ',ai-kb' -n '__fish_seen_subcommand_from remember' -l title -r -d 'Capsule title'
complete -c ',ai-kb' -n '__fish_seen_subcommand_from remember' -l body -r -d 'Capsule body'
complete -c ',ai-kb' -n '__fish_seen_subcommand_from remember' -l kind -x -a "$__ai_kb_kinds" -d 'Capsule kind'
complete -c ',ai-kb' -n '__fish_seen_subcommand_from remember' -l scope -x -a "$__ai_kb_scopes" -d 'Capsule scope'
complete -c ',ai-kb' -n '__fish_seen_subcommand_from remember' -l source -r -d 'Evidence anchor'
complete -c ',ai-kb' -n '__fish_seen_subcommand_from remember' -l tags -r -d 'CSV tags'
complete -c ',ai-kb' -n '__fish_seen_subcommand_from remember' -l workspace -r -a '(__fish_complete_directories)' -d 'Workspace path'
complete -c ',ai-kb' -n '__fish_seen_subcommand_from remember' -l project -r -d 'Project id'
complete -c ',ai-kb' -n '__fish_seen_subcommand_from remember' -l domain -r -d 'Domain tag'
complete -c ',ai-kb' -n '__fish_seen_subcommand_from remember' -l confidence -r -d 'Confidence 0..1'
complete -c ',ai-kb' -n '__fish_seen_subcommand_from remember' -l verified-by -r -d 'Verifier reference'
complete -c ',ai-kb' -n '__fish_seen_subcommand_from remember' -l supersedes -r -d 'Capsule id replaced'
complete -c ',ai-kb' -n '__fish_seen_subcommand_from remember' -l refs -r -d 'Related capsule or external ref'
complete -c ',ai-kb' -n '__fish_seen_subcommand_from remember' -l no-embed -d 'Skip embedding'
complete -c ',ai-kb' -n '__fish_seen_subcommand_from remember' -l json -d 'Emit JSON'

complete -c ',ai-kb' -n '__fish_seen_subcommand_from search' -l limit -r -d 'Maximum hits'
complete -c ',ai-kb' -n '__fish_seen_subcommand_from search' -l scope -x -a "$__ai_kb_scopes" -d 'Filter scope'
complete -c ',ai-kb' -n '__fish_seen_subcommand_from search' -l kind -x -a "$__ai_kb_kinds" -d 'Filter kind'
complete -c ',ai-kb' -n '__fish_seen_subcommand_from search' -l workspace -r -a '(__fish_complete_directories)' -d 'Workspace bias'
complete -c ',ai-kb' -n '__fish_seen_subcommand_from search' -l domain -r -d 'Filter domain'
complete -c ',ai-kb' -n '__fish_seen_subcommand_from search' -l mode -x -a "$__ai_kb_modes" -d 'Search mode'
complete -c ',ai-kb' -n '__fish_seen_subcommand_from search' -l json -d 'Emit JSON'

complete -c ',ai-kb' -n '__fish_seen_subcommand_from get list curate ingest harvest' -l json -d 'Emit JSON'
complete -c ',ai-kb' -n '__fish_seen_subcommand_from list reembed' -l limit -r -d 'Limit rows'
complete -c ',ai-kb' -n '__fish_seen_subcommand_from curate' -l no-dedupe -d 'Skip dedupe pass'
complete -c ',ai-kb' -n '__fish_seen_subcommand_from curate' -l no-decay -d 'Skip decay pass'
complete -c ',ai-kb' -n '__fish_seen_subcommand_from curate' -l no-contradictions -d 'Skip contradiction scan'
complete -c ',ai-kb' -n '__fish_seen_subcommand_from curate' -l dedupe-threshold -r -d 'Dedupe cosine threshold'
complete -c ',ai-kb' -n '__fish_seen_subcommand_from curate' -l contradiction-threshold -r -d 'Contradiction cosine threshold'
complete -c ',ai-kb' -n '__fish_seen_subcommand_from curate' -l decay-step -r -d 'Decay increment'
complete -c ',ai-kb' -n '__fish_seen_subcommand_from ingest' -l scope -x -a "$__ai_kb_scopes" -d 'Capsule scope'
complete -c ',ai-kb' -n '__fish_seen_subcommand_from ingest' -l workspace -r -a '(__fish_complete_directories)' -d 'Workspace path'
complete -c ',ai-kb' -n '__fish_seen_subcommand_from ingest' -l domain -r -d 'Domain tag'
complete -c ',ai-kb' -n '__fish_seen_subcommand_from ingest' -l max-bytes -r -d 'Maximum input bytes'
complete -c ',ai-kb' -n '__fish_seen_subcommand_from ingest' -a '(__fish_complete_path)' -d 'Markdown file or directory'

complete -c ',ai-kb' -n '__fish_seen_subcommand_from harvest' -l workspace -r -a '(__fish_complete_directories)' -d 'Workspace path (default: cwd)'
complete -c ',ai-kb' -n '__fish_seen_subcommand_from harvest' -l topic -r -d 'Topic name (default: active topic)'
complete -c ',ai-kb' -n '__fish_seen_subcommand_from harvest' -l worklog -r -a '(__fish_complete_path)' -d 'Explicit worklog path'
complete -c ',ai-kb' -n '__fish_seen_subcommand_from harvest' -l min-repeats -r -d 'Occurrences before a repeat is a candidate'
complete -c ',ai-kb' -n '__fish_seen_subcommand_from harvest' -l limit -r -d 'Maximum candidates shown'
