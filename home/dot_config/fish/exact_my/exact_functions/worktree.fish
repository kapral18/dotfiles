function _get_worktree_parent_dir
    set -l git_common_dir (realpath (git rev-parse --git-common-dir))
    set -l main_repo_root (dirname $git_common_dir)
    dirname $main_repo_root
end

function _print_created_worktree_message
    echo "

-------------

Created new worktree
For Branch: $argv[1]
At Path: $argv[2]"

    if test -n "$argv[3]"
        echo "From Branch: $argv[3]"
    else
        echo "From Current Branch"
    end
end

function _add_worktree_tmux_session
    if test -n "$TMUX"
        echo "

-------------

Adding TMUX Session: $argv[1]|$argv[2]
At Path: $argv[3]
"
        # add tmux session
        tmux new-session -d -s "$argv[1]|$argv[2]" -c $argv[3]
    end
end

function _remove_worktree_tmux_session
    if test -n "$TMUX"

        set -l worktree_path $argv[1]

        set -l session_name $(tmux list-sessions -F "#{session_name} #{session_path}" | grep -i "$worktree_path" | awk "{print \$1}")

        echo "

-------------

Removing TMUX Session: $session_name
"
        if test -n "$session_name"
            tmux kill-session -t $session_name
        end
    end
end

function add_worktree --description "Add a worktree for a branch"
    if test (count $argv) -eq 0
        echo "Usage: add_worktree <branch_name> [base_branch]"
        return 1
    end

    set -l branch_name "$argv[1]"

    set -l parent_dir (_get_worktree_parent_dir) # Get the parent directory for the worktree
    set -l parent_name (basename $parent_dir)

    if git worktree list | grep -qw "$branch_name"
        echo "Branch '$branch_name' already exists as a worktree."
        return
    end

    set -l branch_name_split (_get_split_branch_name $branch_name)
    set -l inferred_branch_remote $branch_name_split[1]
    set -l inferred_branch_name $branch_name_split[2]
    set -l prefixed_branch_name "$inferred_branch_remote"__"$inferred_branch_name"

    if git worktree list | grep -qw "$prefixed_branch_name"
        echo "Branch '$prefixed_branch_name' already exists as a worktree."
        return
    end

    set -l is_base_branch_specified (test (count $argv) -eq 2; and echo 1; or echo 0)

    if test "$is_base_branch_specified" -gt 0
        set -l base_branch_split (_get_split_branch_name "$base_branch")
        set -l inferred_base_branch_remote "$base_branch_split[1]"

        if string match -q -r "\b$inferred_base_branch_remote__$branch_name\b" -- (git worktree list)
            echo "Branch '$inferred_base_branch_remote"__"$branch_name' already exists as a worktree."
            return
        end
    end

    set -l worktree_path "$parent_dir/$branch_name"

    if string match -q -r "\b$inferred_branch_remote\b" -- (git remote)
        git fetch $inferred_branch_remote $inferred_branch_name
    end

    # only-branch-specified case
    if test "$is_base_branch_specified" -eq 0
        # Check if the branch exists locally
        if git show-ref --verify --quiet "refs/heads/$branch_name"
            # GIVEN feat/test-1 branch DOES exist locally
            #
            # WHEN add_worktree feat/test-1 is called
            #
            # THEN feat/test-1 branched worktree at feat/test-1 path SHOULD be created reusing feat/test-1 local branch

            echo "Branch '$branch_name' already exists locally. Reusing it."

            git worktree add $worktree_path $branch_name

            _add_worktree_tmux_session "$parent_name" "$branch_name" "$worktree_path"

            echo "

            -------------

            Created new worktree
            For Local Branch: $branch_name
            At Path: $worktree_path"

        else if git show-ref --quiet --verify "refs/heads/$inferred_branch_name" && git rev-parse --abbrev-ref @{u} | grep -q "$inferred_branch_remote/"
            # GIVEN feat/test-1 branch DOES exist locally
            #
            # AND it looks on the remote like origin/feat/test-1 (this makes sure feat/test-1 looking at other_upstrea/feat/test-1 is not considered)
            #
            # WHEN add_worktree origin/feat/test-1 is called
            #
            # THEN feat/test-1 branched worktree at feat/test-1 path SHOULD be created reusing feat/test-1 local branch
            #
            # OR
            #
            # GIVEN feat/test-1 branch DOES exist locally
            #
            # AND it looks on the remote like upstream/feat/test-1
            #
            # WHEN add_worktree upstream/feat/test-1 is called
            #
            # THEN feat/test-1 branched worktree at feat/test-1 path SHOULD be created reusing feat/test-1 local branch

            echo "Branch '$inferred_branch_name' already exists locally. Reusing it."

            git worktree add $worktree_path $inferred_branch_name

            _add_worktree_tmux_session "$parent_name" "$inferred_branch_name" "$worktree_path"

            echo "

            -------------

            Created new worktree
            For Local Branch: $inferred_branch_name
            At Path: $worktree_path"

        else if git show-ref --quiet --verify "refs/heads/$inferred_branch_remote"__"$inferred_branch_name"
            # GIVEN other_upstream__feat/test-1 branch DOES exist locally
            #
            # WHEN add_worktree other_upstream__feat/test-1 is called
            #
            # THEN other_upstream__feat/test-1 branched worktree at other_upstream/feat/test-1 path SHOULD be created reusing other_upstream__feat/test-1 local branch

            set worktree_path "$parent_dir/$inferred_branch_remote/$inferred_branch_name"

            echo "Branch '$prefixed_branch_name' already exists locally. Reusing it."

            git worktree add $worktree_path $prefixed_branch_name

            _add_worktree_tmux_session "$parent_name" "$prefixed_branch_name" "$worktree_path"

            echo "

            -------------

            Created new worktree
            For Local Branch: $prefixed_branch_name
            At Path: $worktree_path"

        else if git show-ref --quiet --verify "refs/remotes/origin/$branch_name"
            # GIVEN feat/test-1 branch DOES NOT exist locally
            # AND
            # GIVEN feat/test-1 branch DOES exist on origin remote
            #
            # WHEN add_worktree feat/test-1 is called
            #
            # THEN feat/test-1 branched worktree at feat/test-1 path SHOULD be created from origin/feat/test-1 remote branch

            git worktree add "$worktree_path" -b "$branch_name" "origin/$branch_name"

            _add_worktree_tmux_session "$parent_name" "$branch_name" "$worktree_path"
            _print_created_worktree_message "$branch_name" "$worktree_path" "origin/$branch_name"

        else if git show-ref --quiet --verify "refs/remotes/upstream/$branch_name"
            # GIVEN feat/test-1 branch DOES NOT exist locally
            # AND
            # GIVEN feat/test-1 branch DOES NOT exist on origin remote
            # AND
            # GIVEN feat/test-1 branch DOES exist on upstream remote
            #
            # WHEN add_worktree feat/test-1 is called
            #
            # THEN feat/test-1 branched worktree at feat/test-1 path SHOULD be created from upstream/feat/test-1 remote branch

            git worktree add "$worktree_path" -b "$branch_name" "upstream/$branch_name"

            _add_worktree_tmux_session "$parent_name" "$branch_name" "$worktree_path"
            _print_created_worktree_message "$branch_name" "$worktree_path" "upstream/$branch_name"

        else if git show-ref --quiet --verify "refs/remotes/$branch_name"

            if string match -q -r "\b(origin|upstream)\b" -- $inferred_branch_remote

                # GIVEN origin/feat/test-1 branch DOES exist
                #
                # WHEN add_worktree origin/feat/test-1 is called
                #
                # THEN feat/test-1 branched worktree at feat/test-1 path SHOULD be created from origin/feat/test-1 remote branch
                #
                # OR
                #
                # GIVEN upstream/feat/test-1 branch DOES exist
                #
                # WHEN add_worktree upstream/feat/test-1 is called
                #
                # THEN feat/test-1 branched worktree at feat/test-1 path SHOULD be created from upstream/feat/test-1 remote branch

                set worktree_path "$parent_dir/$inferred_branch_name"

                git worktree add "$worktree_path" -b "$inferred_branch_name" "$branch_name"

                _add_worktree_tmux_session "$parent_name" "$inferred_branch_name" "$worktree_path"
                _print_created_worktree_message "$inferred_branch_name" "$worktree_path" "$branch_name"

            else
                # GIVEN other_upstream/feat/test-1 branch DOES exist
                #
                # WHEN add_worktree other_upstream/feat/test-1 is called
                #
                # THEN other_upstream__feat/test-1 branched worktree at other_upstream/feat/test-1 path SHOULD be created from other_upstream/feat/test-1 remote branch

                set worktree_path "$parent_dir/$inferred_branch_remote/$inferred_branch_name"

                git worktree add $worktree_path -b "$prefixed_branch_name" "$branch_name"

                _add_worktree_tmux_session "$parent_name" "$prefixed_branch_name" "$worktree_path"
                _print_created_worktree_message "$prefixed_branch_name" "$worktree_path" "$branch_name"
            end
        else
            # GIVEN feat/test-1 branch DOES NOT exist locally
            # AND
            # GIVEN feat/test-1 branch DOES NOT exist on any remote
            #
            # WHEN add_worktree feat/test-1 is called
            #
            # THEN feat/test-1 branched worktree at feat/test-1 path SHOULD be created from current HEAD

            git worktree add $worktree_path -b $branch_name

            _add_worktree_tmux_session "$parent_name" "$branch_name" "$worktree_path"
            _print_created_worktree_message "$branch_name" "$worktree_path"
        end
    else
        # Validate the preexisting $branch_name

        # Check if branch_name already exists locally
        if git show-ref --verify --quiet "refs/heads/$branch_name"
            # GIVEN feat/test-1 DOES exist locally
            #
            # WHEN add_worktree feat/test-1 $base_branch is called
            #
            # THEN SHOULD NOT create a new worktree and SHOULD return an error

            echo "Branch '$branch_name' already exists locally."
            echo "Cannot create a new branch with the same name."
            return 1

        else if git show-ref --quiet --verify "refs/remotes/origin/$branch_name"
            # GIVEN feat/test-1 branch DOES exist on origin remote
            #
            # WHEN add_worktree feat/test-1 $base_branch is called
            #
            # THEN SHOULD NOT create a new worktree and SHOULD return an error

            echo "Branch '$branch_name' already exists on 'origin' remote."
            echo "Cannot create a new branch with the same name."
            return 1

        else if git show-ref --quiet --verify "refs/remotes/upstream/$branch_name"
            # GIVEN feat/test-1 DOES exist on upstream remote
            #
            # WHEN add_worktree feat/test-1 $base_branch is called
            #
            # THEN SHOULD NOT create a new worktree and SHOULD return an error

            echo "Branch '$branch_name' already exists on 'upstream' remote."
            echo "Cannot create a new branch with the same name."
            return 1

        else if git show-ref --quiet --verify "refs/remotes/$branch_name"
            # GIVEN feat/test-1 DOES exist on another remote
            #
            # WHEN add_worktree feat/test-1 $base_branch is called
            #
            # THEN SHOULD NOT create a new worktree and SHOULD return an error
            echo "Branch '$branch_name' already exists on a remote."
            echo "Cannot create a new branch with the same name."
            return 1
        end

        if string match -q -r "\b$infered_branch_remote\b" -- (git remote)
            echo "WHEN using base branch argument, main branch arugment SHOULD NOT include a remote name. Please provide a valid branch name."

            echo "For example, instead of add_worktree $branch_name $base_branch, use add_worktree $inferred_branch_name $base_branch."
            return 1
        end

        set -l base_branch_split (_get_split_branch_name $base_branch)
        set -l inferred_base_branch_remote $base_branch_split[1]
        set -l inferred_base_branch_name $base_branch_split[2]

        if string match -q -r "\b$inferred_base_branch_remote\b" -- (git remote)
            git fetch $inferred_base_branch_remote $inferred_base_branch_name
        end

        # Now validate the $base_branch

        # Check if base_branch exists locally
        if git show-ref --verify --quiet "refs/heads/$base_branch"
            # GIVEN feat/test-1 DOES exist locally
            #
            # WHEN add_worktree feat/test-2 feat/test-1 is called
            #
            # THEN feat/test-2 branched worktree at feat/test-2 path SHOULD be created from feat/test-1 local branch

            git worktree add "$worktree_path" -b "$branch_name" "$base_branch"

            _add_worktree_tmux_session "$parent_name" "$branch_name" "$worktree_path"
            _print_created_worktree_message "$branch_name" "$worktree_path" "$base_branch"

        else if git show-ref --quiet --verify "refs/remotes/origin/$base_branch"
            # GIVEN base_branch exists on origin remote
            #
            # WHEN add_worktree feat/test-2 feat/test-1 is called
            #
            # THEN feat/test-2 branched worktree at feat/test-2 path SHOULD be created from origin/feat/test-1 remote branch

            git worktree add "$worktree_path" -b "$branch_name" "origin/$base_branch"

            _add_worktree_tmux_session "$parent_name" "$branch_name" "$worktree_path"
            _print_created_worktree_message "$branch_name" "$worktree_path" "origin/$base_branch"

        else if git show-ref --quiet --verify "refs/remotes/upstream/$base_branch"
            # GIVEN base_branch exists on upstream remote
            #
            # WHEN add_worktree feat/test-2 feat/test-1 is called
            #
            # THEN feat/test-2 branched worktree at feat/test-2 path SHOULD be created from upstream/feat/test-1 remote branch

            git worktree add "$worktree_path" -b "$branch_name" "upstream/$base_branch"

            _add_worktree_tmux_session "$parent_name" "$branch_name" "$worktree_path"
            _print_created_worktree_message "$branch_name" "$worktree_path" "upstream/$base_branch"

        else if git show-ref --quiet --verify "refs/remotes/$base_branch"
            # GIVEN origin/feat/test-1 branch DOES exist
            #
            # WHEN add_worktree feat/test-2 origin/feat/test-1 is called
            #
            # THEN feat/test-2 branched worktree at feat/test-2 path SHOULD be created from other_remote/feat/test-1 remote branch

            set worktree_path "$parent_dir/$inferred_base_branch_remote/$branch_name"
            git worktree add "$worktree_path" -b "$inferred_base_branch_remote__$branch_name" "$base_branch"

            _add_worktree_tmux_session "$parent_name" "$inferred_base_branch_remote__$branch_name" "$worktree_path"
            _print_created_worktree_message "$branch_name" "$worktree_path" "$base_branch"
        else
            # GIVEN feat/test-1 DOES NOT exist locally
            #
            # WHEN add_worktree feat/test-2 feat/test-1 is called
            #
            # THEN SHOULD NOT create a new worktree and SHOULD return an error
            echo "Base branch '$base_branch' does not exist."
            return 1
        end
    end

    # Add the new worktree to zoxide
    zoxide add "$worktree_path"
end

# Helper function to get the number of positional arguments
function __fish_add_worktree_positional_arg_count
    set -l argv (commandline -opc)
    set -l count 0
    for arg in $argv
        if not string match -qr '^-' -- $arg
            set count (math $count + 1)
        end
    end
    # If the cursor is after a space, we need to increment count
    set -l cursor_char (commandline -ct)
    if test "$cursor_char" = ""
        set count (math $count + 1)
    end
    echo $count
end

# Helper function to check if we are completing positional argument N
# @fish-lsp-disable-next-line 4004
function __fish_add_worktree_is_nth_positional_arg
    set -l n $argv[1]
    if test -z "$n"
        return 1
    end
    set -l count (__fish_add_worktree_positional_arg_count)
    if test $count -eq $n
        return 0
    else
        return 1
    end
end

# Completion for the first positional argument (branch_name)
complete -c add_worktree -n '__fish_add_worktree_is_nth_positional_arg 1' -f -a '(git for-each-ref --format="%(refname:strip=2)" refs/heads/ refs/remotes/)'

# Completion for the second positional argument (base_branch)
complete -c add_worktree -n '__fish_add_worktree_is_nth_positional_arg 2' -f -a '(git for-each-ref --format="%(refname:strip=2)" refs/heads/ refs/remotes/)'

# @fish-lsp-disable-next-line 4004
function get_pr_worktrees --description "Fetch PRs from GitHub and create a worktree for each"
    set -l pr_numbers

    if string match -qr '^[0-9]+$' -- $argv[1]
        set pr_numbers $argv[1]
    else
        # Search and select PR using fzf with improved preview (multi-select enabled)
        set pr_numbers (gh pr list --search "$argv[1]" --json number,title \
        --jq '.[] | "\(.number) \(.title)"' | fzf --multi --preview '
            gh pr view {1} --json number,title,body,author,labels,comments --template "
# PR #{{.number}}: {{.title}}

---

## Author: {{.author.login}}

{{range .labels}}- {{.name}} {{end}}

---


{{.body}}" | bat --style=auto --color always --wrap never --paging never --language Markdown
        ' --preview-window="right:70%:nowrap" --ansi | awk "{print \$1}")
    end

    if test -z "$pr_numbers"
        echo "No PR selected."
        return 1
    end

    # Process each selected PR
    for pr_number in $pr_numbers
        echo "Processing PR #$pr_number..."

        # Fetch PR details using GitHub CLI
        set -l pr_info (gh pr view $pr_number --json headRefName,headRepository,headRepositoryOwner \
            --jq '.headRefName + " " + .headRepository.name + " " + .headRepositoryOwner.login')

        # Extract branch name, repository name, and owner
        set -l branch_name (echo $pr_info | cut -d ' ' -f1)
        if test -z "$branch_name"
            echo "No branch name found in PR #$pr_number info."
            continue
        end
        set -l repo_name (echo $pr_info | cut -d ' ' -f2)
        if test -z "$repo_name"
            echo "No repository name found in PR #$pr_number info."
            continue
        end
        set -l repo_owner (echo $pr_info | cut -d ' ' -f3)
        if test -z "$repo_owner"
            echo "No repository owner found in PR #$pr_number info."
            continue
        end

        set -l upstream_remote_owner (git remote get-url upstream | awk -F'[:/]' "{print \$2}")

        if test $repo_owner = $upstream_remote_owner
            echo "PR #$pr_number is from the upstream repository. Setting the remote to 'upstream'..."
            set repo_owner upstream
        end

        set -l repo_url "git@github.com:$repo_owner/$repo_name.git"

        # Add remote if it doesn't exist
        if not git remote get-url $repo_owner >/dev/null 2>&1
            git remote add $repo_owner $repo_url
        end

        add_worktree "$repo_owner/$branch_name"
        echo "Completed PR #$pr_number worktree creation."
    end
end

# @fish-lsp-disable-next-line 4004
function remove_worktrees --description "Remove multiple worktrees using fzf and delete the associated branches"
    set -l worktrees (git worktree list -v | fzf --no-preview --ansi --multi)

    if test -z "$worktrees"
        echo "No worktrees selected."
        return 1
    end

    set -l default_branch (git config --get init.defaultbranch)
    set -l remotes_to_check

    for worktree in $worktrees
        set -l worktree_path (echo $worktree | awk "{print \$1}")
        # @fish-lsp-disable-next-line 2001
        set -l worktree_branch (echo $worktree | awk '{
            last = $NF
            gsub(/^[[(]|[])]$/, "", last)
            print last
        }')

        # if the worktree_branch is HEAD then it's a detached HEAD
        # so we skip it
        if test $worktree_branch = HEAD
            echo "Skipping worktree at '$worktree_path'. It's in detached HEAD state."
            continue
        end

        if test $worktree_branch = $default_branch
            echo "Skipping default branch at '$worktree_path'"
            continue
        end

        echo "Removing worktree: $worktree_path ($worktree_branch)"
        git worktree remove $worktree_path

        # collect remotes for later cleanup
        set remote_branch (git rev-parse --abbrev-ref $worktree_branch@{upstream} 2>/dev/null)
        if test -n "$remote_branch"
            set remote (echo $remote_branch | cut -d'/' -f1)
            if test -n "$remote"; and not test "$remote" = origin; and not test "$remote" = upstream
                set -a remotes_to_check $remote
            end
        end

        # check if branch still appears in other worktrees
        if git worktree list --porcelain | grep branch | grep -qw "$worktree_branch"
            echo "Branch '$worktree_branch' is still used by other worktrees, skipping deletion."
        else
            git branch -D $worktree_branch
        end

        _remove_worktree_tmux_session $worktree_path

        # cleanup all remaining empty scaffold, for example if the branch was named fix/DQD/fix-blabla
        # it would've created a fix/DQD folder in the worktree_path which would remain after worktree deletion
        # so we recursively clean up all empty directories first "DQD" then "fix" checking if they are empty
        # and removing them if they are until we reach the first non-empty parent directory
        set -l current_dir $(dirname $worktree_path)
        # we need to string join the output of ls -A to check if it's empty
        # because ls -A will output the files space separated which test -z
        # will interpret as a list of arguments
        while test -z "$(ls -A $current_dir | string join ' ')"
            set -l parent_dir (dirname $current_dir)
            rmdir $current_dir
            set current_dir $parent_dir
        end

        zoxide remove $worktree_path
    end

    # cleanup remotes that are no longer referenced by any worktree
    for remote in (printf '%s\n' $remotes_to_check | sort -u)
        if not string match -q -r "\b$remote\b" -- (git worktree list -v)
            echo "Removing unused remote: $remote"
            git remote remove $remote
        end
    end
end
