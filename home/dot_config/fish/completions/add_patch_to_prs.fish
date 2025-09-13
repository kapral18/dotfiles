complete -c add_patch_to_prs --no-files \
    -d "Add patch to PRs" \
    -a "(gh pr list --json number --jq '.[].number')"
