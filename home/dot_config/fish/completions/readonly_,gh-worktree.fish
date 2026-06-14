set -l __gh_worktree_kinds pr issue

complete -c ',gh-worktree' -f
complete -c ',gh-worktree' -s h -l help -d 'Show help'
complete -c ',gh-worktree' -n "not __fish_seen_subcommand_from $__gh_worktree_kinds" -a pr -d 'Checkout PR worktree'
complete -c ',gh-worktree' -n "not __fish_seen_subcommand_from $__gh_worktree_kinds" -a issue -d 'Checkout issue worktree'
complete -c ',gh-worktree' -l repo-path -r -a '(__fish_complete_directories)' -d 'Repo path hint'
complete -c ',gh-worktree' -l focus -d 'Focus tmux session'
complete -c ',gh-worktree' -l quiet -d 'Pass quiet mode to ,w'
complete -c ',gh-worktree' -l branch -r -d 'Issue branch base name'
complete -c ',gh-worktree' -l create-bg -d 'Run PR checkout in background'
complete -c ',gh-worktree' -l print-root -d 'Print root worktree path'
complete -c ',gh-worktree' -l no-bootstrap -d 'Fail if repo is missing'
