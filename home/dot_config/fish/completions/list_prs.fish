complete -c list_prs --no-files \
    -d "List GitHub PRs" \
    -a "(gh pr list --json state,title --jq '.[] | select(.state == \"OPEN\") | .title')"
