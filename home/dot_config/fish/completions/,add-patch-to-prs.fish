complete -c ,add-patch-to-prs --no-files \
    -d "Add patch to PRs" \
    -a "(gh pr list --json number --jq '.[].number')"
