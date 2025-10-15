if not functions -q __f_add_worktree_args_before_cursor
  function __f_add_worktree_args_before_cursor
    set -l tokens (commandline -opc)
    set -l args
    set -l after_double_dash 0

    for token in $tokens
      if test $after_double_dash -eq 1
        set args $args $token
        continue
      end

      switch $token
        case '--'
          set after_double_dash 1
        case '-q' '--quiet'
          continue
        case '-*'
          continue
        case '*'
          set args $args $token
      end
    end

    echo $args
  end
end

complete -c f-add-worktree -f
complete -c f-add-worktree -s q -l quiet -d 'Suppress informational output'
complete -c f-add-worktree --no-files -n 'set -l args (__f_add_worktree_args_before_cursor); test (count $args) -eq 0' -a '(git for-each-ref --format="%(refname:strip=2)" refs/heads refs/remotes 2>/dev/null)' -d 'Branch name'
complete -c f-add-worktree --no-files -n 'set -l args (__f_add_worktree_args_before_cursor); test (count $args) -eq 1' -a '(git for-each-ref --format="%(refname:strip=2)" refs/heads refs/remotes 2>/dev/null)' -d 'Base branch'
