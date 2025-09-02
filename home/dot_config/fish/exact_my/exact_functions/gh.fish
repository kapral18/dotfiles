function _check_rate_limit
    set -l remaining (_safe_exec_cmd gh api rate_limit --jq '.rate.remaining')
    or return 1

    if test $remaining -lt 100
        echo "Warning: GitHub API rate limit is low ($remaining remaining)" >&2
        return 1
    end
end

function search_gh_topic --description "Search GitHub topics"
    if test (count $argv) -eq 0
        echo "Usage: search_gh_topic <search_query> [topic]"
        return 1
    end

    set -l SEARCH_QUERY $argv[1]
    set -l TOPIC $argv[2]
    set -q TOPIC[1]; or set TOPIC gh-extension

    echo "Searching GitHub for '$SEARCH_QUERY' with topic '$TOPIC'..."

    gh search repos "$SEARCH_QUERY" --topic "$TOPIC" --limit 50 | fzf --preview 'gh repo view {1}' | awk '{print $1}' | xargs -I_ open "https://github.com/_"
end

function list_prs --description "List PRs using GitHub CLI"
    if test (count $argv) -eq 0
        gh pr list --limit 100 --json number,title --jq '.[] | "\(.number)\t\(.title)"' || true
    else
        gh pr list --search "$argv[1]" --json number,title --jq '.[] | "\(.number)\t\(.title)"' || true
    end
end

function remove_comment --description "Remove a comment from current PR using gh and fzf"
    set -l COMMENT_TEMPLATE \
        'Author: {{.user.login}}
Updated At: {{.updated_at }}

{{.body}}'
    set -l OWNER_REPO (gh repo view --json owner,name --template '{{.owner.login}}/{{.name}}')
    set -l SELECTED_COMMENT_ID (gh pr view --json comments --jq '.comments.[].url' \
        | awk -F'#issuecomment-' '{print $2}' \
        | fzf --preview "gh api repos/$OWNER_REPO/issues/comments/{} --template '$COMMENT_TEMPLATE'")

    gh api --method DELETE /repos/$OWNER_REPO/issues/comments/$SELECTED_COMMENT_ID
end

function _is_auto_merge_enabled
    set pr_number $argv[1]
    set auto_merge_enabled (_safe_exec_cmd gh pr view $pr_number --json autoMergeRequest --jq '.autoMergeRequest != null')
    or return 1
    test "$auto_merge_enabled" = true
end

function is_pr_commented
    set pr_number $argv[1]
    set comment_body (_safe_exec_cmd gh pr view $pr_number --json comments --jq '.comments[].body')
    or return 1
    string match -q "*Please do not merge this pull request*" "$comment_body"
end

function _process_single_pr
    set -l pr_number $argv[1]
    set -l actions_performed false

    if not is_pr_commented $pr_number
        echo "PR #$pr_number: Adding comment"
        if not _safe_exec_cmd gh pr comment $pr_number --body "We have disabled auto-merge for this PR. Please do not merge this pull request. We will re-enable auto-merge once the PR is ready for merging."
            return 1
        end
        set actions_performed true
    end

    if _is_auto_merge_enabled $pr_number
        echo "PR #$pr_number: Disabling auto-merge"
        if not _safe_exec_cmd gh pr merge $pr_number --disable-auto
            return 1
        end
        set actions_performed true
    end

    if $actions_performed
        echo "Processed PR #$pr_number"
    else
        echo "Skipping PR #$pr_number: Already fully processed"
    end
    return 0
end

# Disable auto-merge for PRs targeting a specified branch
# Usage: auto_disable_prs <base_branch> [skip_pr_numbers...]
# Example: auto_disable_prs 8.x 1234 5678
function disable_auto_merge --description "Automatically disable auto-merge for PRs targeting a specified branch"
    if not _check_rate_limit
        echo "Aborting due to rate limit concerns"
        return 1
    end

    if test (count $argv) -lt 1
        echo "Usage: auto_disable_prs <base_branch> [skip_pr_numbers...]"
        return 1
    end

    set -l base_branch $argv[1]
    set -l skip_prs $argv[2..-1]

    set prs (_safe_exec_cmd gh pr list --base $base_branch --state open --json number --jq '.[].number')
    or return 1

    for pr_number in $prs
        if contains -- $pr_number $skip_prs
            echo "Skipping PR #$pr_number: Excluded from processing"
            continue
        end

        echo "Processing PR #$pr_number..."
        if not _process_single_pr $pr_number
            echo "Failed to process PR #$pr_number, continuing with next PR"
            continue
        end
    end
end

function enable_auto_merge --description "Automatically enable auto-merge for PRs targeting a specified branch"
    if not _check_rate_limit
        echo "Aborting due to rate limit concerns"
        return 1
    end

    if test (count $argv) -lt 1
        echo "Usage: auto_disable_prs <base_branch>"
        return 1
    end

    set -l base_branch $argv[1]

    set prs (_safe_exec_cmd gh pr list --base $base_branch --state open --json number --jq '.[].number')
    or return 1

    for pr_number in $prs
        echo "Processing PR #$pr_number..."

        if _is_auto_merge_enabled $pr_number
            echo "PR #$pr_number: Auto-merge is already enabled"
            continue
        end

        _safe_exec_cmd gh pr merge $pr_number --auto --squash
        or continue

        _safe_exec_cmd gh pr comment $pr_number --body "Auto-merge has been re-enabled. Thank you for your patience."
        or continue

        echo "Re-enabled auto-merge for PR #$pr_number"
    end
end

function remove_wrong_comments --description "Remove comments with specific content from PRs"
    if not _check_rate_limit
        echo "Aborting due to rate limit concerns"
        return 1
    end

    set -l pr_numbers (_safe_exec_cmd gh pr list --base 8.x --state open --json number --jq '.[].number')
    or return 1

    set -l message_to_remove "Auto-merge has been re-enabled. Thank you for your patience. :heart:"

    for pr in $pr_numbers
        echo "Processing PR #$pr"

        set -l comments (_safe_exec_cmd gh pr view $pr --json comments --jq '.comments[].id')
        or continue

        for comment_id in $comments
            set -l comment_body (_safe_exec_cmd gh pr view $pr --json comments --jq ".comments[] | select(.id == $comment_id).body")
            or continue

            if string match -q "*$message_to_remove*" "$comment_body"
                echo "Removing comment $comment_id from PR #$pr"
                _safe_exec_cmd gh pr comment $pr --delete "$comment_id"
            end
        end
    end

    echo "Finished processing all PRs"
end

function view_my_issues --description "View your GitHub issues using fzf"
    gh issue list --assignee @me --limit 100 --json number,title \
        --jq '.[] | "\(.number)\t\(.title)"' |
        fzf --delimiter="\t" --with-nth=2 |
        cut -f1 |
        xargs -r gh issue view --web
end
