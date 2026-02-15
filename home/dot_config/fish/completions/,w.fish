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
        case '-q' '--quiet' '--focus' '--awaiting' '--dirty' '--long' '--full-path' '--no-header' '--no-column' '--apply' '--all' '--keep-path'
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

if not functions -q __comma_w_is_completing_option
  function __comma_w_is_completing_option
    set -l cur (commandline -ct 2>/dev/null)
    test -n "$cur"; and string match -qr '^-+' -- $cur
  end
end

if not functions -q __comma_w_prs_candidates
  function __comma_w_prs_candidates
    command -sq git; or return
    git rev-parse --is-inside-work-tree >/dev/null 2>&1; or return
    command -sq gh; or return
    command -sq ,w; or return

    # If the current token looks like an option (e.g. "--aw"), don't run any
    # slow PR-listing commands; let fish complete flags quickly.
    set -l cur (commandline -ct)
    if test -n "$cur"
      if string match -qr '^-+' -- $cur
        return
      end
    end

    set -l tokens (commandline -opc)
    if contains -- '--awaiting' $tokens
      ,w prs --awaiting --complete 2>/dev/null
      return
    end

    gh pr list --limit 200 --json number,title --jq '.[] | "\(.number)\t\(.title)"' 2>/dev/null
  end
end

if not functions -q __comma_w_selectable_worktrees
  function __comma_w_selectable_worktrees
    if __comma_w_is_completing_option
      return
    end

    command -sq git; or return
    git rev-parse --is-inside-work-tree >/dev/null 2>&1; or return

    # Prefer the ,w implementation so we match its notion of selectable worktrees.
    command -sq ,w; or return
    ,w ls --selectable 2>/dev/null
  end
end

if not functions -q __comma_w_complete_branches_and_remotes
  function __comma_w_complete_branches_and_remotes
    if __comma_w_is_completing_option
      return
    end

    command -sq git; or return
    git for-each-ref --format="%(refname:strip=2)" refs/heads refs/remotes 2>/dev/null
  end
end

if not functions -q __comma_w_complete_branches
  function __comma_w_complete_branches
    if __comma_w_is_completing_option
      return
    end

    command -sq git; or return
    git for-each-ref --format="%(refname:strip=2)" refs/heads 2>/dev/null
  end
end

if not functions -q __comma_w_selectable_worktree_branches
  function __comma_w_selectable_worktree_branches
    for line in (__comma_w_selectable_worktrees)
      set -l parts (string split -m 1 '\t' -- $line)
      set -l branch $parts[1]
      set -l path $parts[2]
      test -n "$branch"; or continue
      printf '%s\t%s\n' $branch $path
    end
  end
end

if not functions -q __comma_w_selectable_worktree_paths
  function __comma_w_selectable_worktree_paths
    for line in (__comma_w_selectable_worktrees)
      set -l parts (string split -m 1 '\t' -- $line)
      set -l branch $parts[1]
      set -l path $parts[2]
      test -n "$path"; or continue
      printf '%s\t%s\n' $path $branch
    end
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
complete -c ,w -n '__fish_seen_subcommand_from add; and set -l args (__comma_w_args_before_cursor); and test (count $args) -eq 1' -a '(__comma_w_complete_branches_and_remotes)' -d 'Branch name'
complete -c ,w -n '__fish_seen_subcommand_from add; and set -l args (__comma_w_args_before_cursor); and test (count $args) -eq 2' -a '(__comma_w_complete_branches_and_remotes)' -d 'Base branch'

complete -c ,w -n '__fish_seen_subcommand_from prs' -s q -l quiet -d 'Suppress informational output'
complete -c ,w -n '__fish_seen_subcommand_from prs' -l focus -d 'Switch/attach to tmux session'
complete -c ,w -n '__fish_seen_subcommand_from prs' -l awaiting -d 'Awaiting my/team review (autocomplete: last 7 days)'
complete -c ,w -n '__fish_seen_subcommand_from prs; and set -l args (__comma_w_args_before_cursor); and test (count $args) -eq 1' -a '(__comma_w_prs_candidates)' -d 'PR number'

complete -c ,w -n '__fish_seen_subcommand_from ls list' -l porcelain -d 'Print porcelain worktree list'
complete -c ,w -n '__fish_seen_subcommand_from ls list' -l selectable -d 'Print branch<TAB>path'
complete -c ,w -n '__fish_seen_subcommand_from ls list' -l long -d 'Include ahead/behind'
complete -c ,w -n '__fish_seen_subcommand_from ls list' -l dirty -d 'Compute dirty state (slow)'
complete -c ,w -n '__fish_seen_subcommand_from ls list' -l full-path -d 'Do not shorten paths'
complete -c ,w -n '__fish_seen_subcommand_from ls list' -l no-header -d 'Omit header row'
complete -c ,w -n '__fish_seen_subcommand_from ls list' -l no-column -d 'Do not align with column'
complete -c ,w -n '__fish_seen_subcommand_from ls list' -l sort -x -a 'branch path' -d 'Sort rows'

complete -c ,w -n '__fish_seen_subcommand_from switch' -s q -l quiet -d 'Suppress informational output'
complete -c ,w -n '__fish_seen_subcommand_from switch; and set -l args (__comma_w_args_before_cursor); and test (count $args) -eq 1' -a '(__comma_w_selectable_worktree_branches)' -d 'Worktree branch'

complete -c ,w -n '__fish_seen_subcommand_from open' -s q -l quiet -d 'Suppress informational output'
complete -c ,w -n '__fish_seen_subcommand_from open; and set -l args (__comma_w_args_before_cursor); and test (count $args) -eq 1' -a '(__comma_w_selectable_worktree_branches)' -d 'Worktree branch'
complete -c ,w -n '__fish_seen_subcommand_from open; and set -l args (__comma_w_args_before_cursor); and test (count $args) -eq 1' -a '(__comma_w_selectable_worktree_paths)' -d 'Worktree path'

complete -c ,w -n '__fish_seen_subcommand_from mv' -s q -l quiet -d 'Suppress informational output'
complete -c ,w -n '__fish_seen_subcommand_from mv' -l focus -d 'Switch/attach to tmux session'
complete -c ,w -n '__fish_seen_subcommand_from mv' -l keep-path -d 'Do not move directory'
complete -c ,w -n '__fish_seen_subcommand_from mv' -l path -x -d 'Override destination path'
complete -c ,w -n '__fish_seen_subcommand_from mv; and set -l args (__comma_w_args_before_cursor); and test (count $args) -eq 1' -a '(__comma_w_selectable_worktree_branches)' -d 'From worktree branch'
complete -c ,w -n '__fish_seen_subcommand_from mv; and set -l args (__comma_w_args_before_cursor); and test (count $args) -eq 1' -a '(__comma_w_selectable_worktree_paths)' -d 'From worktree path'
complete -c ,w -n '__fish_seen_subcommand_from mv; and set -l args (__comma_w_args_before_cursor); and test (count $args) -eq 2' -a '(__comma_w_complete_branches)' -d 'To branch'

complete -c ,w -n '__fish_seen_subcommand_from prune' -s q -l quiet -d 'Suppress informational output'
complete -c ,w -n '__fish_seen_subcommand_from prune' -l apply -d 'Apply pruning actions'
complete -c ,w -n '__fish_seen_subcommand_from prune' -l all -d 'Prune tmux sessions across repos'

complete -c ,w -n '__fish_seen_subcommand_from doctor' -d 'Check dependencies and state'

complete -c ,w -n '__fish_seen_subcommand_from remove' -d "Remove worktrees interactively"
