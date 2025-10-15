if not functions -q __f_get_pr_worktrees_args_before_cursor
  function __f_get_pr_worktrees_args_before_cursor
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

complete -c f-get-pr-worktrees -f
complete -c f-get-pr-worktrees -s q -l quiet -d 'Suppress informational output'
complete -c f-get-pr-worktrees --no-files -d 'PR number or search term'
complete -c f-get-pr-worktrees --no-files -n 'set -l args (__f_get_pr_worktrees_args_before_cursor); test (count $args) -eq 0' -a '(gh pr list --limit 200 --json number,title --jq ".[] | \"\(.number)\t\(.title)\"" 2>/dev/null)' -d 'PR number'
