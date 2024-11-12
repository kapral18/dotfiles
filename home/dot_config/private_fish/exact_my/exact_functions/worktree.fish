function _get_worktree_parent_dir
    set -l parent_dir ".."
    if test -f (git rev-parse --show-toplevel)/.git
        set -l git_common_dir (git rev-parse --git-common-dir)
        set -l main_repo_root (dirname $git_common_dir)
        set parent_dir (dirname $main_repo_root)
    end
    echo $parent_dir
end

function _print_created_worktree_message
    echo "

    -------------

    Created new worktree
    For Branch: $argv[1]
    From Remote Branch: $argv[2]
    On Remote: $argv[3]
    At Path: $argv[4]"
end

function add_worktree --description "Add a worktree for a branch"
    if test (count $argv) -eq 0
        echo "Usage: add_worktree <branch_name> [base_branch]"
        return 1
    end

    set -l is_base_branch_specified (test (count $argv) -eq 2; and echo 1; or echo 0)

    set -l branch_name $argv[1]
    set -l default_local_branch (basename (git rev-parse --abbrev-ref origin/HEAD))
    # Set the base branch to the default branch of the origin remote
    # Because any other remote base branch should be explicitly specified
    set base_branch $default_local_branch

    if test $is_base_branch_specified -eq 1
        set base_branch $argv[2]
    end

    if git worktree list | grep -qw "$branch_name"
        echo "Branch '$branch_name' already exists as a worktree."
        return
    end

    # Determine the parent directory for the new worktree
    set parent_dir (_get_worktree_parent_dir)

    # is second argument was not provided, we assume base_branch is the default local branch
    # for origin remote and hence we make assumptions against origin only
    if test $is_base_branch_specified -eq 0
        if git show-ref --verify --quiet "refs/heads/$branch_name" # Check if the branch exists locally
            # case: add_worktree feat/test-1
            # given feat/test-1 exists locally
            # feat/test-1 worktree should be created from feat/test-1 local branch

            echo "Branch '$branch_name' already exists locally. Reusing it."
            git worktree add "$parent_dir/$branch_name" "$branch_name"

            echo "

            -------------

            Created new worktree
            For Local Branch: $branch_name
            At Path: $parent_dir/$branch_name"

        else if git show-ref --quiet --verify "refs/remotes/origin/$branch_name"
            # case: add_worktree feat/test-1
            # given feat/test-1 exists on origin remote
            # feat/test-1 worktree should be created from origin/feat/test-1 remote

            git worktree add "$parent_dir/$branch_name" -b "$branch_name" "origin/$branch_name"

            _print_created_worktree_message $branch_name "origin/$branch_name" origin "$parent_dir/$branch_name"

        else if git show-ref --quiet --verify "refs/remotes/$branch_name" # Check if the branch exists on upstream remote
            # case: add_worktree upstream/feat/test-1
            # given feat/test-1 exists on upstream remote
            # feat/test-1 worktree with upstream__feat/test-1 branch should be created from upstream/feat/test-1 remote

            set -l split_branch_name (string split -m 1 / $branch_name)
            set -l inferred_remote_name $split_branch_name[1]
            set -l inferred_branch_name $split_branch_name[2]
            set -l composite_branch_name "$inferred_remote_name"__"$inferred_branch_name"
            git worktree add "$parent_dir/$inferred_branch_name" -b "$composite_branch_name" "$branch_name"

            _print_created_worktree_message $composite_branch_name $branch_name $inferred_remote_name "$parent_dir/$inferred_branch_name"

        else
            # case: add_worktree feat/test-1 
            #
            # given feat/test-1 doesn't exist locally
            # and feat/test-1 doesn't exist on any remote
            # feat/test-1 worktree should be created from the default local branch (ex. main)

            git worktree add "$parent_dir/$branch_name" -b "$branch_name" $default_local_branch

            _print_created_worktree_message $branch_name $default_local_branch origin "$parent_dir/$branch_name"
        end
    else
        if git show-ref --verify --quiet "refs/heads/$base_branch" # Check if the base branch exists locally
            # case: add_worktree feat/test-2 feat/test-1
            # given feat/test-1 exists locally
            # feat/test-2 worktree should be created from feat/test-1 local branch

            git worktree add "$parent_dir/$branch_name" "$base_branch"

            echo "

            -------------

            Created new worktree
            For Local Branch: $branch_name
            From Local Branch: $base_branch
            At Path: $parent_dir/$branch_name"

        else if git show-ref --quiet --verify "refs/remotes/origin/$base_branch"
            # case: add_worktree feat/test-2 feat/test-1
            # given feat/test-1 exists on origin remote only
            # feat/test-2 worktree should be created from origin/feat/test-1 remote

            git worktree add "$parent_dir/$branch_name" -b "$branch_name" "origin/$base_branch"

            _print_created_worktree_message $branch_name "origin/$base_branch" origin "$parent_dir/$branch_name"

        else if git show-ref --quiet --verify "refs/remotes/$base_branch"
            # case: add_worktree feat/test-2 upstream/feat/test-1
            # given feat/test-1 exists on upstream remote
            # feat/test-2 worktree with upstream__feat/test-2 branch should be created from upstream/feat/test-1 remote

            set -l split_branch_name (string split -m 1 / $base_branch)
            set -l inferred_remote_name $split_branch_name[1]
            set -l inferred_branch_name $split_branch_name[2]
            set -l composite_branch_name "$inferred_remote_name"__"$branch_name"
            git worktree add "$parent_dir/$branch_name" -b "$composite_branch_name" "$base_branch"

            _print_created_worktree_message $composite_branch_name $base_branch $inferred_remote_name "$parent_dir/$branch_name"

        else
            # case: add_worktree feat/test-2 feat/test-1
            #
            # given feat/test-1 doesn't exist locally
            # and feat/test-1 doesn't exist on any remote
            # we should exit with an error message

            echo "Base branch '$base_branch' doesn't exist locally or on any remote."
            return 1
        end
    end

    # Add the new worktree to zoxide
    zoxide add "$parent_dir/$branch_name"
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

    set -l remote $repo_owner
    set -l remote_branch "$remote/$branch_name"
    set -l local_branch "$remote"__"$branch_name"
    set -l worktree_path "$parent_dir/$repo_owner/$branch_name"
    # Create the worktree in the parent directory
    # Set local branch to be able to do things like gh pr view --web
    # Use remote in the local branch name to avoid conflicts between
    # branches with the same name from different remotes
    git worktree add $worktree_path -b $local_branch $remote_branch

    echo "
    -------------

    Created worktree for PR #$pr_number
    Local Branch: $local_branch
    Remote: $remote
    Worktree Path: $worktree_path"

    zoxide add $worktree_path
end

function remove_pr_worktree --description "Remove a worktree using fzf and delete the associated branch"
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
