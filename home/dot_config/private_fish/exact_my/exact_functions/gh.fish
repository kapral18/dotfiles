function search_gh_topic --description "Search GitHub topics"
    if test (count $argv) -eq 0
        echo "Usage: search_gh_topic <search_query> [topic]"
        return 1
    end

    set -l search_query $argv[1]
    set -l topic $argv[2]
    set -q topic[1]; or set topic gh-extension

    echo "Searching GitHub for '$search_query' with topic '$topic'..."

    gh search repos "$search_query" --topic "$topic" --limit 50 | fzf --preview 'gh repo view {1}' | awk '{print $1}' | xargs -I_ open "https://github.com/_"
end

function list_prs --description "List PRs using GitHub CLI"
    if test (count $argv) -eq 0
        gh pr list --limit 100 --json number,title --jq '.[] | "\(.number)\t\(.title)"' || true
    else
        gh pr list --search "$argv[1]" --json number,title --jq '.[] | "\(.number)\t\(.title)"' || true
    end
end
