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
    set -l remote_branch_remote $remote_branch_split[1]
    set -l remote_branch_name $remote_branch_split[2]

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

function pull_rebase --description 'Pull the latest changes from the remote and rebase'
    set -l current_branch (git branch --show-current)
    set -l fork_upstream (git reflog show $current_branch | grep 'branch: Created from' | awk "{print \$NF}")

    # if the fork_upstream is empty or HEAD, it means the branch was created locally
    # so we need to find the upstream branch on origin
    if test -z "$fork_upstream" -o "$fork_upstream" = HEAD
        set fork_upstream (git branch -r --contains $current_branch | grep 'origin/' | grep -v 'HEAD' | awk "{print \$1}")

        # if the fork_upstream is empty, try to git fetch the upstream branch
        if test -z "$fork_upstream"
            echo "Could not find the forked upstream branch, trying to fetch it from origin"
            git fetch origin $current_branch
            set fork_upstream (git branch -r --contains $current_branch | grep 'origin/' | grep -v 'HEAD' | awk "{print \$1}")
        end
    end

    if test -z "$fork_upstream"
        echo "Could not find the forked upstream branch"
        return 1
    end

    set -l upstream_split (_get_split_branch_name $fork_upstream)
    set -l upstream_remote $upstream_split[1]
    set -l upstream_branch $upstream_split[2]

    if test -z "$upstream_remote" -o -z "$upstream_branch"
        echo "Could not find $fork_upstream remote or branch"
        return 1
    end

    # ask for confirmation
    echo "Pulling the latest changes from $upstream_remote/$upstream_branch and rebasing on top of it"

    if not _confirm
        return 1
    end

    git pull --rebase $upstream_remote $upstream_branch
end
