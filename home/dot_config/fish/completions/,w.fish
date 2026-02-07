if not functions -q __comma_w_args_before_cursor
  function __comma_w_args_before_cursor
    set -l tokens (commandline -opc)
    set -l args
    set -l after_double_dash 0
    set -l skip_next 0

    for token in $tokens
      if test $skip_next -eq 1
        set skip_next 0
        continue
      end

      if test $after_double_dash -eq 1
        set args $args $token
        continue
      end

      switch $token
        case '--'
          set after_double_dash 1
        case '-q' '--quiet' '--focus' '--dirty' '--long' '--full-path' '--no-header' '--no-column' '--apply' '--all' '--keep-path'
          continue
        case '--sort' '--path'
          set skip_next 1
          continue
        case '-*'
          continue
        case ',w'
          continue
        case '*'
          set args $args $token
      end
    end

    echo $args
  end
end

complete -c ,w -f

complete -c ,w -s h -l help -d 'Show help'

complete -c ,w -n 'not __fish_seen_subcommand_from add prs ls list switch open mv prune doctor remove' -a 'add' -d 'Add a worktree for a branch'
complete -c ,w -n 'not __fish_seen_subcommand_from add prs ls list switch open mv prune doctor remove' -a 'prs' -d 'Fetch PRs and create worktrees'
complete -c ,w -n 'not __fish_seen_subcommand_from add prs ls list switch open mv prune doctor remove' -a 'ls' -d 'List worktrees'
complete -c ,w -n 'not __fish_seen_subcommand_from add prs ls list switch open mv prune doctor remove' -a 'list' -d 'List worktrees'
complete -c ,w -n 'not __fish_seen_subcommand_from add prs ls list switch open mv prune doctor remove' -a 'switch' -d 'Switch to a worktree tmux session'
complete -c ,w -n 'not __fish_seen_subcommand_from add prs ls list switch open mv prune doctor remove' -a 'open' -d 'Open a worktree tmux session'
complete -c ,w -n 'not __fish_seen_subcommand_from add prs ls list switch open mv prune doctor remove' -a 'mv' -d 'Move/rename a worktree'
complete -c ,w -n 'not __fish_seen_subcommand_from add prs ls list switch open mv prune doctor remove' -a 'prune' -d 'Prune stale worktree metadata/tmux'
complete -c ,w -n 'not __fish_seen_subcommand_from add prs ls list switch open mv prune doctor remove' -a 'doctor' -d 'Check dependencies and state'
complete -c ,w -n 'not __fish_seen_subcommand_from add prs ls list switch open mv prune doctor remove' -a 'remove' -d 'Remove worktrees interactively'

complete -c ,w -n '__fish_seen_subcommand_from add' -s q -l quiet -d 'Suppress informational output'
complete -c ,w -n '__fish_seen_subcommand_from add; and set -l args (__comma_w_args_before_cursor); and test (count $args) -eq 1' -a '(git for-each-ref --format="%(refname:strip=2)" refs/heads refs/remotes 2>/dev/null)' -d 'Branch name'
complete -c ,w -n '__fish_seen_subcommand_from add; and set -l args (__comma_w_args_before_cursor); and test (count $args) -eq 2' -a '(git for-each-ref --format="%(refname:strip=2)" refs/heads refs/remotes 2>/dev/null)' -d 'Base branch'

complete -c ,w -n '__fish_seen_subcommand_from prs' -s q -l quiet -d 'Suppress informational output'
complete -c ,w -n '__fish_seen_subcommand_from prs' -l focus -d 'Switch/attach to tmux session'
complete -c ,w -n '__fish_seen_subcommand_from prs; and set -l args (__comma_w_args_before_cursor); and test (count $args) -eq 1' -a '(gh pr list --limit 200 --json number,title --jq ".[] | \"\(.number)\t\(.title)\"" 2>/dev/null)' -d 'PR number'

complete -c ,w -n '__fish_seen_subcommand_from ls list' -l porcelain -d 'Print porcelain worktree list'
complete -c ,w -n '__fish_seen_subcommand_from ls list' -l selectable -d 'Print branch<TAB>path'
complete -c ,w -n '__fish_seen_subcommand_from ls list' -l long -d 'Include ahead/behind'
complete -c ,w -n '__fish_seen_subcommand_from ls list' -l dirty -d 'Compute dirty state (slow)'
complete -c ,w -n '__fish_seen_subcommand_from ls list' -l full-path -d 'Do not shorten paths'
complete -c ,w -n '__fish_seen_subcommand_from ls list' -l no-header -d 'Omit header row'
complete -c ,w -n '__fish_seen_subcommand_from ls list' -l no-column -d 'Do not align with column'
complete -c ,w -n '__fish_seen_subcommand_from ls list' -l sort -x -a 'branch path' -d 'Sort rows'

complete -c ,w -n '__fish_seen_subcommand_from switch' -s q -l quiet -d 'Suppress informational output'

complete -c ,w -n '__fish_seen_subcommand_from open' -s q -l quiet -d 'Suppress informational output'
complete -c ,w -n '__fish_seen_subcommand_from open; and set -l args (__comma_w_args_before_cursor); and test (count $args) -eq 1' -a '(git worktree list --porcelain 2>/dev/null | awk "/^branch refs\\/heads\\//{sub(\"branch refs\\/heads/\", \"\"); print} /^worktree /{sub(\"worktree \", \"\"); print}")' -d 'Branch or path'

complete -c ,w -n '__fish_seen_subcommand_from mv' -s q -l quiet -d 'Suppress informational output'
complete -c ,w -n '__fish_seen_subcommand_from mv' -l focus -d 'Switch/attach to tmux session'
complete -c ,w -n '__fish_seen_subcommand_from mv' -l keep-path -d 'Do not move directory'
complete -c ,w -n '__fish_seen_subcommand_from mv' -l path -x -d 'Override destination path'
complete -c ,w -n '__fish_seen_subcommand_from mv; and set -l args (__comma_w_args_before_cursor); and test (count $args) -eq 1' -a '(git worktree list --porcelain 2>/dev/null | awk "/^branch refs\\/heads\\//{sub(\"branch refs\\/heads/\", \"\"); print} /^worktree /{sub(\"worktree \", \"\"); print}")' -d 'From branch or path'
complete -c ,w -n '__fish_seen_subcommand_from mv; and set -l args (__comma_w_args_before_cursor); and test (count $args) -eq 2' -a '(git for-each-ref --format="%(refname:strip=2)" refs/heads 2>/dev/null)' -d 'To branch'

complete -c ,w -n '__fish_seen_subcommand_from prune' -s q -l quiet -d 'Suppress informational output'
complete -c ,w -n '__fish_seen_subcommand_from prune' -l apply -d 'Apply pruning actions'
complete -c ,w -n '__fish_seen_subcommand_from prune' -l all -d 'Prune tmux sessions across repos'

complete -c ,w -n '__fish_seen_subcommand_from doctor' -d 'Check dependencies and state'

complete -c ,w -n '__fish_seen_subcommand_from remove' -d "Remove worktrees interactively"
