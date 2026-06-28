# Completions for ,artifact.

set -l __artifact_subcommands path write open poll list theme live clean stop
set -l __artifact_live_subcommands start script

function __artifact_names
    ,artifact list 2>/dev/null | python3 -c 'import json,sys; data=json.load(sys.stdin); [print(item["name"]) for item in data.get("artifacts", []) if item.get("name")]' 2>/dev/null
end

complete -c ',artifact' -f

complete -c ',artifact' -n "not __fish_seen_subcommand_from $__artifact_subcommands" \
    -a path -d 'Print cached artifact path'
complete -c ',artifact' -n "not __fish_seen_subcommand_from $__artifact_subcommands" \
    -a write -d 'Write stdin or file to cached artifact'
complete -c ',artifact' -n "not __fish_seen_subcommand_from $__artifact_subcommands" \
    -a open -d 'Open cached artifact review page'
complete -c ',artifact' -n "not __fish_seen_subcommand_from $__artifact_subcommands" \
    -a poll -d 'Wait for browser feedback'
complete -c ',artifact' -n "not __fish_seen_subcommand_from $__artifact_subcommands" \
    -a list -d 'List cached artifacts'
complete -c ',artifact' -n "not __fish_seen_subcommand_from $__artifact_subcommands" \
    -a theme -d 'Show detected ambient artifact theme'
complete -c ',artifact' -n "not __fish_seen_subcommand_from $__artifact_subcommands" \
    -a live -d 'Prepare a feedback overlay for an already-open live page'
complete -c ',artifact' -n "not __fish_seen_subcommand_from $__artifact_subcommands" \
    -a clean -d 'Remove cached artifacts'
complete -c ',artifact' -n "not __fish_seen_subcommand_from $__artifact_subcommands" \
    -a stop -d 'Stop background artifact server'

complete -c ',artifact' -n '__fish_seen_subcommand_from path open poll' \
    -x -a '(__artifact_names)' -d 'Artifact name'
complete -c ',artifact' -n '__fish_seen_subcommand_from write' \
    -x -d 'Artifact name'
complete -c ',artifact' -n '__fish_seen_subcommand_from live; and not __fish_seen_subcommand_from $__artifact_live_subcommands' \
    -x -a start -d 'Start server and print live overlay script URL'
complete -c ',artifact' -n '__fish_seen_subcommand_from live; and not __fish_seen_subcommand_from $__artifact_live_subcommands' \
    -x -a script -d 'Print live overlay JavaScript'
complete -c ',artifact' -n '__fish_seen_subcommand_from live; and __fish_seen_subcommand_from $__artifact_live_subcommands' \
    -x -d 'Live overlay artifact name'

complete -c ',artifact' -n '__fish_seen_subcommand_from write' -s f -l file -r -d 'Read HTML from file'
complete -c ',artifact' -n '__fish_seen_subcommand_from write open' -s t -l title -x -d 'Starter title'
complete -c ',artifact' -n '__fish_seen_subcommand_from write' -l open -d 'Open after writing'
complete -c ',artifact' -n '__fish_seen_subcommand_from write' -l no-theme -d 'Skip ambient theme injection'
complete -c ',artifact' -n '__fish_seen_subcommand_from open' -l no-open -d 'Print URL without opening browser'
complete -c ',artifact' -n '__fish_seen_subcommand_from poll' -l timeout -x -d 'Seconds to wait'
complete -c ',artifact' -n '__fish_seen_subcommand_from theme' -l json -d 'Print theme metadata as JSON'
complete -c ',artifact' -n '__fish_seen_subcommand_from theme' -l css -d 'Print injectable CSS style block'
complete -c ',artifact' -n '__fish_seen_subcommand_from live start' -l json -d 'Print live overlay metadata as JSON'
complete -c ',artifact' -n '__fish_seen_subcommand_from clean' -l all -d 'Remove all agent artifact cache'
