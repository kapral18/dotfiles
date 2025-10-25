if not functions -q __f_wtree_args_before_cursor
  function __f_wtree_args_before_cursor
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
        case 'f-wtree'
          continue
        case '*'
          set args $args $token
      end
    end

    echo $args
  end
end

complete -c f-wtree -f

complete -c f-wtree -n 'not __fish_seen_subcommand_from add prs remove' -a 'add' -d 'Add a worktree for a branch'
complete -c f-wtree -n 'not __fish_seen_subcommand_from add prs remove' -a 'prs' -d 'Fetch PRs and create worktrees'
complete -c f-wtree -n 'not __fish_seen_subcommand_from add prs remove' -a 'remove' -d 'Remove worktrees interactively'

complete -c f-wtree -n '__fish_seen_subcommand_from add' -s q -l quiet -d 'Suppress informational output'
complete -c f-wtree -n '__fish_seen_subcommand_from add; and set -l args (__f_wtree_args_before_cursor); and test (count $args) -eq 1' -a '(git for-each-ref --format="%(refname:strip=2)" refs/heads refs/remotes 2>/dev/null)' -d 'Branch name'
complete -c f-wtree -n '__fish_seen_subcommand_from add; and set -l args (__f_wtree_args_before_cursor); and test (count $args) -eq 2' -a '(git for-each-ref --format="%(refname:strip=2)" refs/heads refs/remotes 2>/dev/null)' -d 'Base branch'

complete -c f-wtree -n '__fish_seen_subcommand_from prs' -s q -l quiet -d 'Suppress informational output'
complete -c f-wtree -n '__fish_seen_subcommand_from prs' -d 'PR number or search term'
complete -c f-wtree -n '__fish_seen_subcommand_from prs; and set -l args (__f_wtree_args_before_cursor); and test (count $args) -eq 1' -a '(gh pr list --limit 200 --json number,title --jq ".[] | \"\(.number)\t\(.title)\"" 2>/dev/null)' -d 'PR number'

complete -c f-wtree -n '__fish_seen_subcommand_from remove' -d "Remove worktrees interactively"
