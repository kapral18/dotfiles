# Custom Commands

Back: [`docs/categories/index.md`](index.md)

This setup ships a collection of small, purpose-built CLI commands into `~/bin`.

## Where They Live

- Source: [`home/exact_bin/`](../../home/exact_bin/)
- Install target: `~/bin/`

Anything named `executable_,something` becomes a command called `,something`.

If you are an IDE-first user: you can run these from VSCode/JetBrains terminal
without switching editors.

## How To Discover Commands

List the installed commands:

```bash
ls -1 "$HOME/bin" | rg '^,'
```

See where a command comes from:

```bash
command -v ,w
```

Show usage for a command:

```bash
,w --help
```

## Useful Aliases

This setup also defines a few cross-shell aliases (Fish + Bash/Zsh).

- `dash`: shorthand for `gh dash`

## High-Leverage Workflows

### System health check: `,doctor`

- Source:
  [`home/exact_bin/executable_,doctor`](../../home/exact_bin/executable_,doctor)
- Checks: chezmoi state, Homebrew, shell, tmux+TPM, git+signing, SSH agent,
  pass/GPG, editors, AI tools, key CLIs, worktrees.

Examples:

```bash
,doctor            # full check
,doctor --quiet    # only warnings/failures
,doctor --verbose  # extra detail (e.g. outdated Homebrew count)
```

### Worktree workflow: `,w`

- Source: [`home/exact_bin/executable_,w`](../../home/exact_bin/executable_,w)
- Helpers: [`home/exact_bin/utils/,w/`](../../home/exact_bin/utils/,w/)

Examples:

```bash
,w add feat/my-change main
,w prs 12345
,w issue 12345
,w switch
,w doctor
```

### PR lookup/open: `,gh-prw`

- Source:
  [`home/exact_bin/executable_,gh-prw`](../../home/exact_bin/executable_,gh-prw)
- Note: attempts to resolve merged PRs even if the remote branch was deleted.

Examples:

```bash
,gh-prw
,gh-prw --number
,gh-prw --url
```

### Issue lookup/open: `,gh-issuew`

- Source:
  [`home/exact_bin/executable_,gh-issuew`](../../home/exact_bin/executable_,gh-issuew)
- Note: infers issue from branch suffix, worktree metadata, or PR body mentions.

Examples:

```bash
,gh-issuew
,gh-issuew --number
,gh-issuew --url
```

### Apply one patch across multiple PRs: `,add-patch-to-prs`

- Source:
  [`home/exact_bin/executable_,add-patch-to-prs`](../../home/exact_bin/executable_,add-patch-to-prs)
- Behavior: applies one patch file across selected PRs; if you do not pass PR
  numbers, it opens an interactive multi-select picker.

Examples:

```bash
,add-patch-to-prs ./fix.patch 12345 12346
,add-patch-to-prs ./fix.patch --search "is:open author:@me"
,add-patch-to-prs ./fix.patch --message "Apply follow-up fix"
```

### Fork + clone + tmux: `,gh-tfork`

- Source:
  [`home/exact_bin/executable_,gh-tfork`](../../home/exact_bin/executable_,gh-tfork)
- Clone target:
  - `~/work/<repo>/<default-branch>` when owner is `elastic`
  - `~/code/<repo>/<default-branch>` otherwise
- For `elastic/kibana`: date-anchored shallow history
  (`--shallow-since=2022-01-01 --no-tags`)
- tmux session: `<wrapper/repo>|<default-branch>` (2 windows, 2 panes each)

Examples:

```bash
,gh-tfork elastic/integrations
```

### Sync branch with upstream: `,pull-rebase`

- Source:
  [`home/exact_bin/executable_,pull-rebase`](../../home/exact_bin/executable_,pull-rebase)
- Behavior: resolves branch upstream and runs `git pull --rebase` with a
  confirmation prompt.

### Re-converge npm globals: `,install-npm-pkgs`

- Source:
  [`home/exact_bin/executable_,install-npm-pkgs`](../../home/exact_bin/executable_,install-npm-pkgs)
- Input list: `~/.default-npm-pkgs` (rendered from
  [`home/readonly_dot_default-npm-pkgs`](../../home/readonly_dot_default-npm-pkgs))

### Apply icon mapping: `,apply-app-icons`

- Source:
  [`home/exact_bin/executable_,apply-app-icons.tmpl`](../../home/exact_bin/executable_,apply-app-icons.tmpl)
- Reads mapping/assets from the repo source directory under
  [`home/app_icons/`](../../home/app_icons/).

### Run one command across tmux sessions: `,tmux-run-all`

- Source:
  [`home/exact_bin/executable_,tmux-run-all`](../../home/exact_bin/executable_,tmux-run-all)

Examples:

```bash
,tmux-run-all "work-*" "git status"
,tmux-run-all --all "work-*" "npm run test -- --watch=false"
```

### Start/control lowfi in tmux: `,tmux-lowfi`

- Source:
  [`home/exact_bin/executable_,tmux-lowfi`](../../home/exact_bin/executable_,tmux-lowfi)

Examples:

```bash
,tmux-lowfi p
,tmux-lowfi nt
,tmux-lowfi q
```

## Additional Commands

### GitHub / PR helpers

| Command                    | Description                                                                                                            |
| -------------------------- | ---------------------------------------------------------------------------------------------------------------------- |
| `,view-my-issues`          | Browse your GitHub issues with fzf preview                                                                             |
| `,remove-comment`          | Delete a comment from the current PR via fzf picker                                                                    |
| `,gh-subissues-create`     | Draft multiple sub-issues in your editor, create them, and attach to a parent issue via GitHub's sub-issue GraphQL API |
| `,check-backport-progress` | Find PRs missing backports or required labels across target branches                                                   |
| `,disable-auto-merge`      | Disable auto-merge for all open PRs targeting a base branch                                                            |
| `,enable-auto-merge`       | Enable auto-merge for all open PRs targeting a base branch                                                             |
| `,trace-string-pr`         | Locate the PR that introduced a matching string and open it in the browser                                             |
| `,hey-branch`              | Quick "am I in sync with upstream?" status (ahead/behind + missing remote)                                             |

### Search / discovery helpers

| Command              | Description                                                                                    |
| -------------------- | ---------------------------------------------------------------------------------------------- |
| `,grepo`             | Grep for a pattern across files and open the selected match in `$EDITOR` at the right line     |
| `,search-brew-desc`  | Search installed Homebrew formula descriptions (JSON output)                                   |
| `,fuzzy-brew-search` | Fuzzy search Homebrew descriptions with preview, then drive an "add this to Brewfile" workflow |
| `,search-gh-topic`   | Search GitHub repos by topic with preview, then open the selected repo                         |

### Testing / analysis helpers

| Command                   | Description                                                                          |
| ------------------------- | ------------------------------------------------------------------------------------ |
| `,jest-test-title-report` | Compare Jest test titles between two worktrees and emit a CSV report                 |
| `,get-risky-tests`        | Run Jest and report tests whose runtime exceeds a threshold                          |
| `,get-age-buckets`        | Compute file "age buckets" from git history to spot stale areas                      |
| `,generate-git-sandbox`   | Create a throwaway git repo with branches/commits for testing rebases/merges/scripts |

### Kibana development helpers

| Command           | Description                                                                                   |
| ----------------- | --------------------------------------------------------------------------------------------- |
| `,start-feat-kbn` | Boot ES (snapshot) and start Kibana in a tmux pane when bootstrap completes (feature cluster) |
| `,start-main-kbn` | Same as above for the "main" cluster defaults/ports                                           |

### Utility helpers

| Command              | Description                                                                                                |
| -------------------- | ---------------------------------------------------------------------------------------------------------- |
| `,cp-files-for-llm`  | Copy a directory tree's text contents to the clipboard with file headers, ready to paste into an assistant |
| `,appid`             | Print the macOS bundle identifier for an app name/path                                                     |
| `,dumputi`           | Dump the system's registered Uniform Type Identifiers                                                      |
| `,to-gif`            | Convert a video to an optimized GIF                                                                        |
| `,vid-ipad`          | Re-encode a video for iPad playback                                                                        |
| `,pdf-diff`          | Visual diff two PDFs by compositing pages                                                                  |
| `,history-sync`      | Merge local Fish history with a 1Password document and push the merged result back                         |

### Internal / plumbing helpers

These are used by other scripts, fzf integrations, and Neovim — you rarely
invoke them directly:

| Command                  | Description                                                                                    |
| ------------------------ | ---------------------------------------------------------------------------------------------- |
| `,bat-preview`           | Smart preview for fzf (images via chafa, binaries via hexyl, directories via ls, text via bat) |
| `,fzf-git-changed-lines` | Emit changed lines as grep-like entries for fzf                                                |
| `,fzf-preview-follow`    | Center fzf preview around a match line                                                         |
| `,fzf-rg-multiline`      | Convert ripgrep output into NUL-delimited multi-line fzf entries                               |

## Verification And Troubleshooting

Quick checks:

```bash
command -v ,w
command -v ,gh-prw
command -v ,tmux-run-all
```

If commands are missing after apply, verify:

- [`home/exact_bin/`](../../home/exact_bin/) contains the source script.
- The script has the `executable_` prefix.
- `chezmoi apply` completed successfully.
- `~/bin` is on `PATH` (`echo "$PATH"`).

## Related

- Worktree workflow:
  [`docs/recipes/worktree-workflow.md`](../recipes/worktree-workflow.md)
- Apply custom app icons:
  [`docs/recipes/apply-custom-app-icons.md`](../recipes/apply-custom-app-icons.md)
- Add a global npm package:
  [`docs/recipes/add-a-global-npm-package.md`](../recipes/add-a-global-npm-package.md)
- Reference map: [`docs/reference-map.md`](../reference-map.md)
