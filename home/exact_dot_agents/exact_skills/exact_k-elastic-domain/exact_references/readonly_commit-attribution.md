# Commit attribution

## Git commit attribution

When the repo belongs to `elastic`, every commit needs a `Co-authored-by` trailer for the AI tool. Use the active tool identity:

- Cursor: `Co-authored-by: Cursor <cursoragent@cursor.com>`
- Claude Code: `Co-authored-by: Claude <noreply@anthropic.com>`
- Copilot: `Co-authored-by: Copilot <noreply@github.com>`
- OpenCode: `Co-authored-by: opencode <noreply@opencode.ai>`
- pi-coding-agent: `Co-authored-by: pi <noreply@anthropic.com>`

If pi already overrides `GIT_AUTHOR_NAME/EMAIL`, skip the trailer to avoid duplication.
If the current tool is unknown, ask for name/email before committing. Append with `git commit --trailer=...`.
