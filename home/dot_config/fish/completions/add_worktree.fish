complete -c add_worktree -f
complete -c add_worktree --no-files -n 'test (count (commandline -xpc)) -eq 1' -a '(git for-each-ref --format="%(refname:strip=2)" refs/heads refs/remotes 2>/dev/null)' -d 'Branch name'
complete -c add_worktree --no-files -n 'test (count (commandline -xpc)) -eq 2' -a '(git for-each-ref --format="%(refname:strip=2)" refs/heads refs/remotes 2>/dev/null)' -d 'Base branch'
