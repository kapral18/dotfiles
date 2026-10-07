set -l __behavior_map_subcommands path show save remove affected check promote resolve drop

function __behavior_map_ids
    ,behavior-map show --ids 2>/dev/null
end

function __behavior_map_branches
    git for-each-ref --format='%(refname:short)' refs/heads 2>/dev/null
end

function __behavior_map_overlays
    set -l root (,behavior-map path 2>/dev/null); or return
    for meta in $root/branches/*/.branch
        string replace -rf '^branch=' '' <$meta
    end
end

function __behavior_map_overlay_ids
    set -l root (,behavior-map path 2>/dev/null); or return
    for entry in $root/branches/*/*/*.md
        string match -qr '\.(base|merge)\.md$' -- $entry; and continue
        string replace -r '.*/([^/]+)/([^/]+)\.md$' '$1/$2' -- $entry
    end
end

complete -c ,behavior-map -f
complete -c ,behavior-map -l repo -x -d 'Map namespace (default: basename of the main checkout)'
complete -c ,behavior-map -l branch -x -a '(__behavior_map_branches)' -d 'Act as this branch'
complete -c ,behavior-map -s h -l help -d 'Show help'
complete -c ,behavior-map -n "not __fish_seen_subcommand_from $__behavior_map_subcommands" -a path -d 'Print the map directory for this repo'
complete -c ,behavior-map -n "not __fish_seen_subcommand_from $__behavior_map_subcommands" -a show -d 'Status line and index, or full entries'
complete -c ,behavior-map -n "not __fish_seen_subcommand_from $__behavior_map_subcommands" -a save -d "Write the entry on stdin to this branch's layer"
complete -c ,behavior-map -n "not __fish_seen_subcommand_from $__behavior_map_subcommands" -a remove -d 'Delete an entry (on a branch: mark it removed)'
complete -c ,behavior-map -n "not __fish_seen_subcommand_from $__behavior_map_subcommands" -a affected -d 'Entries and areas a change touches, and unmapped paths'
complete -c ,behavior-map -n "not __fish_seen_subcommand_from $__behavior_map_subcommands" -a check -d 'List stale, broken, drifted, conflicting entries'
complete -c ,behavior-map -n "not __fish_seen_subcommand_from $__behavior_map_subcommands" -a promote -d 'Merge a branch overlay into the base map'
complete -c ,behavior-map -n "not __fish_seen_subcommand_from $__behavior_map_subcommands" -a resolve -d 'Write a resolved conflict entry to base'
complete -c ,behavior-map -n "not __fish_seen_subcommand_from $__behavior_map_subcommands" -a drop -d 'Delete a branch overlay or one of its entries'
complete -c ,behavior-map -n '__fish_seen_subcommand_from show save remove' -a '(__behavior_map_ids)' -d Entry
complete -c ,behavior-map -n '__fish_seen_subcommand_from show' -l ids -d 'Print entry ids only'
complete -c ,behavior-map -n '__fish_seen_subcommand_from save' -l rebased -d 'Branch entry now builds on the current base entry'
complete -c ,behavior-map -n '__fish_seen_subcommand_from save promote' -l force -d 'Skip the safety check'
complete -c ,behavior-map -n '__fish_seen_subcommand_from affected' -l since -x -d 'Compare against this rev'
complete -c ,behavior-map -n '__fish_seen_subcommand_from affected' -F
complete -c ,behavior-map -n '__fish_seen_subcommand_from check promote' -l offline -d 'Do not ask gh about pull request state'
complete -c ,behavior-map -n '__fish_seen_subcommand_from promote resolve drop; and test (count (commandline -opc)) -le 2' -a '(__behavior_map_overlays)' -d 'Branch overlay'
complete -c ,behavior-map -n '__fish_seen_subcommand_from resolve drop; and test (count (commandline -opc)) -ge 3' -a '(__behavior_map_overlay_ids)' -d 'Overlay entry'
