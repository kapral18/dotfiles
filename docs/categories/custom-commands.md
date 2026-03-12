# Custom Commands

Back: [`docs/categories/index.md`](index.md)

This setup ships a collection of small, purpose-built CLI commands into `~/bin`.

## Where They Live

- Source: `home/exact_bin/`
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

- Source: `home/exact_bin/executable_,doctor`
- Checks: chezmoi state, Homebrew, shell, tmux+TPM, git+signing, SSH agent,
  pass/GPG, editors, AI tools, key CLIs, worktrees.

Examples:

```bash
,doctor            # full check
,doctor --quiet    # only warnings/failures
,doctor --verbose  # extra detail (e.g. outdated Homebrew count)
```

### Worktree workflow: `,w`

- Source: `home/exact_bin/executable_,w`
- Helpers: `home/exact_bin/utils/,w/`

Examples:

```bash
,w add feat/my-change main
,w prs 12345
,w issue 12345
,w switch
,w doctor
```

### PR lookup/open: `,gh-prw`

- Source: `home/exact_bin/executable_,gh-prw`
- Note: attempts to resolve merged PRs even if the remote branch was deleted.

Examples:

```bash
,gh-prw
,gh-prw --number
,gh-prw --url
```

### Issue lookup/open: `,gh-issuew`

- Source: `home/exact_bin/executable_,gh-issuew`
- Note: infers issue from branch suffix, worktree metadata, or PR body mentions.

Examples:

```bash
,gh-issuew
,gh-issuew --number
,gh-issuew --url
```

### Apply one patch across multiple PRs: `,add-patch-to-prs`

- Source: `home/exact_bin/executable_,add-patch-to-prs`
- Behavior: applies one patch file across selected PRs; if you do not pass PR
  numbers, it opens an interactive multi-select picker.

Examples:

```bash
,add-patch-to-prs ./fix.patch 12345 12346
,add-patch-to-prs ./fix.patch --search "is:open author:@me"
,add-patch-to-prs ./fix.patch --message "Apply follow-up fix"
```

### Fork + clone + tmux: `,gh-tfork`

- Source: `home/exact_bin/executable_,gh-tfork`
- Clone target:
  - `~/work/<repo>/<default-branch>` when owner is `elastic`
  - `~/code/<repo>/<default-branch>` otherwise
- For `elastic/kibana`: date-anchored shallow history (`--shallow-since=2022-01-01 --no-tags`)
- tmux session: `<wrapper/repo>|<default-branch>` (2 windows, 2 panes each)

Examples:

```bash
,gh-tfork elastic/integrations
```

### Sync branch with upstream: `,pull-rebase`

- Source: `home/exact_bin/executable_,pull-rebase`
- Behavior: resolves branch upstream and runs `git pull --rebase` with a confirmation prompt.

### Re-converge npm globals: `,install-npm-pkgs`

- Source: `home/exact_bin/executable_,install-npm-pkgs`
- Input list: `~/.default-npm-pkgs` (rendered from `home/readonly_dot_default-npm-pkgs`)

### Apply icon mapping: `,apply-app-icons`

- Source: `home/exact_bin/executable_,apply-app-icons.tmpl`
- Reads mapping/assets from the repo source directory under `home/app_icons/`.

### Run one command across tmux sessions: `,tmux-run-all`

- Source: `home/exact_bin/executable_,tmux-run-all`

Examples:

```bash
,tmux-run-all "work-*" "git status"
,tmux-run-all --all "work-*" "npm run test -- --watch=false"
```

### Start/control lowfi in tmux: `,tmux-lowfi`

- Source: `home/exact_bin/executable_,tmux-lowfi`

Examples:

```bash
,tmux-lowfi p
,tmux-lowfi nt
,tmux-lowfi q
```

## Additional Command Families

- GitHub helpers:
  - `home/exact_bin/executable_,view-my-issues`
  - `home/exact_bin/executable_,add-patch-to-prs`
- Search/discovery helpers:
  - `home/exact_bin/executable_,search-brew-desc`
  - `home/exact_bin/executable_,fuzzy-brew-search`
  - `home/exact_bin/executable_,search-gh-topic`
- Utility helpers:
  - `home/exact_bin/executable_,to-gif`
  - `home/exact_bin/executable_,pdf-diff`
  - `home/exact_bin/executable_,history-sync`

## Verification And Troubleshooting

Quick checks:

```bash
command -v ,w
command -v ,gh-prw
command -v ,tmux-run-all
```

If commands are missing after apply, verify:

- `home/exact_bin/` contains the source script.
- The script has the `executable_` prefix.
- `chezmoi apply` completed successfully.
- `~/bin` is on `PATH` (`echo "$PATH"`).

## Related

- Worktree workflow: [`docs/recipes/worktree-workflow.md`](../recipes/worktree-workflow.md)
- Apply custom app icons: [`docs/recipes/apply-custom-app-icons.md`](../recipes/apply-custom-app-icons.md)
- Add a global npm package: [`docs/recipes/add-a-global-npm-package.md`](../recipes/add-a-global-npm-package.md)
- Reference map: [`docs/reference-map.md`](../reference-map.md)
