complete -c f-get-pr-worktrees -f
complete -c f-get-pr-worktrees --no-files -d 'PR number or search term'
complete -c f-get-pr-worktrees --no-files -n 'test (count (commandline -xpc)) -eq 1' -a '(gh pr list --limit 200 --json number,title --jq ".[] | \"\(.number)\t\(.title)\"" 2>/dev/null)' -d 'PR number'
