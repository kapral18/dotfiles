function _get_worktree_parent_dir
    set -l git_common_dir (realpath (git rev-parse --git-common-dir))
    set -l main_repo_root (dirname $git_common_dir)
    dirname $main_repo_root
end

function _get_split_branch_name
    echo $argv[1] | string split -m 1 /
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

        set -l wizard_session_proof_branch_name (echo $argv[1] | tr '.' '-')
        set -l session_name $(tmux list-sessions -F "#{session_name}" | grep -i "$wizard_session_proof_branch_name")

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

    if git worktree list | grep -qw "$branch_name"
        echo "Branch '$branch_name' already exists as a worktree."
        return
    end

    set -l branch_name "$argv[1]"
    set -l parent_dir (_get_worktree_parent_dir) # Get the parent directory for the worktree
    set -l parent_name (basename $parent_dir)
    set -l is_base_branch_specified (test (count $argv) -eq 2; and echo 1; or echo 0)
    set -l worktree_path "$parent_dir/$branch_name"

    # only-branch-specified case
    if test $is_base_branch_specified -eq 0
        if git show-ref --verify --quiet "refs/heads/$branch_name" # Check if the branch exists locally
            # GIVEN feat/test-1 branch DOES exist locally
            #
            # WHEN add_worktree feat/test-1 is called
            #
            # THEN feat/test-1 branched worktree at feat/test-1 path SHOULD be created reusing feat/test-1 local branch

            echo "Branch '$branch_name' already exists locally. Reusing it."

            _add_worktree_tmux_session "$parent_name" "$branch_name" "$worktree_path"
            git worktree add $worktree_path $branch_name

            echo "

            -------------

            Created new worktree
            For Local Branch: $branch_name
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

            # handle cases when $branch_name includes origin or upstream as above
            set -l branch_name_split (_get_split_branch_name $branch_name)
            set -l inferred_remote_name $branch_name_split[1]
            set -l inferred_branch_name $branch_name_split[2]


            if contains "$inferred_remote_name" origin upstream

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

                echo 'happens here'

                set -l prefixed_branch_name "$inferred_remote_name"__"$inferred_branch_name"
                set worktree_path "$parent_dir/$inferred_branch_name"

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
            # GIVEN feat/test-1 exists on upstream remote
            #
            # WHEN add_worktree feat/test-1 $base_branch is called
            #
            # THEN SHOULD NOT create a new worktree and SHOULD return an error

            echo "Branch '$branch_name' already exists on 'upstream' remote."
            echo "Cannot create a new branch with the same name."
            return 1

        else if git show-ref --quiet --verify "refs/remotes/$branch_name"
            # GIVEN feat/test-1 exists on a other remote
            #
            # WHEN add_worktree feat/test-1 $base_branch is called
            #
            # THEN SHOULD NOT create a new worktree and SHOULD return an error
            echo "Branch '$branch_name' already exists on a remote."
            echo "Cannot create a new branch with the same name."
            return 1
        end

        # Validate the edge case when $branch_name includes remote name

        set -l branch_name_split (_get_split_branch_name $branch_name)
        set -l inferred_branch_remote $branch_name_split[1]
        set -l inferred_branch_name $branch_name_split[2]

        if contains "$inferred_branch_remote" (git remote)
            echo "WHEN using base branch argument, main branch arugment SHOULD NOT include a remote name. Please provide a valid branch name."

            echo "For example, instead of add_worktree $branch_name $base_branch, use add_worktree $inferred_branch_name $base_branch."
            return 1
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

            set -l base_branch_split (_get_split_branch_name $base_branch)
            set -l inferred_base_branch_remote $base_branch_split[1]
            set -l inferred_base_branch_name $base_branch_split[2]

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

function get_pr_worktree --description "Fetch a PR from GitHub and create a worktree for it"
    if test (count $argv) -eq 0
        echo "Usage: get_pr_worktree <search_query>"
        return
    end

    set -l pr_number

    if string match -qr '^[0-9]+$' -- $argv[1]
        set pr_number $argv[1]
    else
        # Search and select PR using fzf with improved preview
        set pr_number (gh pr list --search "$argv[1]" --json number,title \
        --jq '.[] | "\(.number) \(.title)"' | fzf --preview '
            gh pr view {1} --json number,title,body,author,labels,comments --template "
# PR #{{.number}}: {{.title}}

---

## Author: {{.author.login}}

{{range .labels}}- {{.name}} {{end}}

---


{{.body}}" | bat --style=auto --color always --wrap never --paging never --language Markdown
        ' --preview-window="right:70%:nowrap" --ansi | awk '{print $1}')
    end

    if test -z "$pr_number"
        echo "No PR selected."
        return 1
    end

    # Fetch PR details using GitHub CLI
    set -l pr_info (gh pr view $pr_number --json headRefName,headRepository,headRepositoryOwner \
        --jq '.headRefName + " " + .headRepository.name + " " + .headRepositoryOwner.login')

    # Extract branch name, repository name, and owner
    set -l branch_name (echo $pr_info | cut -d ' ' -f1)
    set -l repo_name (echo $pr_info | cut -d ' ' -f2)
    set -l repo_owner (echo $pr_info | cut -d ' ' -f3)

    # Validate extracted information
    for var in branch_name repo_name repo_owner
        if test -z (eval echo \$$var)
            echo "$var is empty"
            return 1
        end
    end

    set -l repo_url "git@github.com:$repo_owner/$repo_name.git"

    # Add remote if it doesn't exist
    if not git remote get-url $repo_owner >/dev/null 2>&1
        git remote add $repo_owner $repo_url
    end

    # Fetch the branch
    git fetch $repo_owner $branch_name

    set -l parent_dir (_get_worktree_parent_dir)
    set -l parent_name (basename $parent_dir)

    set -l remote_branch "$repo_owner/$branch_name"
    set -l local_branch "$repo_owner"__"$branch_name"
    set -l worktree_path "$parent_dir/$repo_owner/$branch_name"
    # Create the worktree in the parent directory
    # Set local branch to be able to do things like gh pr view --web
    # Use remote in the local branch name to avoid conflicts between
    # branches with the same name from different remotes
    git worktree add $worktree_path -b $local_branch $remote_branch

    _add_worktree_tmux_session $parent_name $branch_name $worktree_path
    _print_created_worktree_message $local_branch $worktree_path $remote_branch

    zoxide add $worktree_path
end

function remove_worktree --description "Remove a worktree using fzf and delete the associated branch"
    set -l worktree (git worktree list -v | fzf --no-preview --ansi)

    if test -z "$worktree"
        echo "No worktree selected."
        return 1
    end

    set -l worktree_path (echo $worktree | awk '{print $1}')
    set -l worktree_branch (echo $worktree | awk '{
        last = $NF
        gsub(/^[[(]|[])]$/, "", last)
        print last
    }')

    zoxide remove $worktree_path

    git worktree remove $worktree_path

    # if the worktree_branch is HEAD then it's a detached HEAD
    # so we don't need to delete the branch
    if test $worktree_branch = HEAD
        echo "Removed worktree at '$worktree_path'."
        return
    end

    git branch -D $worktree_branch

    _remove_worktree_tmux_session $worktree_branch

    # cleanup all remaining empty scaffold, for example if the branch was named fix/DQD/fix-blabla
    # it would've created a fix/DQD folder in the worktree_path which would remain after worktree deletion
    # so we recursively clean up all empty directories first "DQD" then "fix" checking if they are empty
    # and removing them if they are until we reach the first non-empty parent directory
    set -l current_dir $(dirname $worktree_path)
    # we need to string join the output of ls -A to check if it's empty
    # because ls -A will output the files space separated which test -z
    # will interpret as a list of arguments
    while test -z (ls -A $current_dir | string join ' ')
        set -l parent_dir (dirname $current_dir)
        rmdir $current_dir
        set current_dir $parent_dir
    end
end
