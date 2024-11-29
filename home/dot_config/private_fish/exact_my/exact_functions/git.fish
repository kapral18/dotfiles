function hey_branch --description 'Check the status of the current branch'
    # Get the current branch name
    set current_branch (git branch --show-current)

    # Get the remote tracking branch
    set remote_branch (git rev-parse --abbrev-ref "$current_branch"@{upstream} 2>/dev/null)

    echo ------------------------------------

    if test -z "$remote_branch"
        echo "Tracked Branch: <missing>"
        return 1
    end

    # Extract the remote name and branch name
    set -l remote_branch_split (_get_split_branch_name $remote_branch)
    set -l inferred_remote_branch_remote $remote_branch_split[1]
    set -l inferred_remote_branch_name $remote_branch_split[2]


    echo "Tracked Branch: '$remote_branch'"

    echo ------------------------------------

    # Fetch the latest information from the remote
    git fetch "$remote_branch_remote" "$remote_branch_name" 2>/dev/null

    # Check if the remote branch still exists
    if git ls-remote --exit-code --heads $remote_branch_remote $remote_branch_name >/dev/null 2>&1
        echo "Tracked Branch Exists: Yes"
        echo ------------------------------------

        # Check if the local branch is up to date with the remote
        set local_commit (git rev-parse HEAD)
        set remote_commit (git rev-parse $remote_branch)

        if test "$local_commit" = "$remote_commit"
            echo "Local Branch In Sync: Yes"
        else
            set behind (git rev-list --count HEAD..$remote_branch)
            set ahead (git rev-list --count $remote_branch..HEAD)
            echo "Local Branch In Sync: No

Behind: $behind commits
Ahead: $ahead commits"
        end

    else
        echo "Tracked Branch Exists: No"
    end

    echo ------------------------------------
end
