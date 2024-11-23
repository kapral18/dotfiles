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
