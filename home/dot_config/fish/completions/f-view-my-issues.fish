complete -c f-view-my-issues --no-files \
    -d "View assigned GitHub issues" \
    -a "(gh issue list --assignee @me --json title --jq '.[].title')"
