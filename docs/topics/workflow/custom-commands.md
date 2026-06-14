---
sidebar_position: 5
---

# Custom Commands

This setup ships a collection of small, purpose-built CLI commands into `~/bin`.

## Where They Live

- Source: [`home/exact_bin/`](../../../home/exact_bin/)
- Install target: `~/bin/`

Anything named `executable_,something` becomes a command called `,something`.

If you are an IDE-first user: you can run these from VSCode/JetBrains terminal without switching editors.

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

- Source: [`home/exact_bin/executable_,doctor`](../../../home/exact_bin/executable_,doctor)
- Checks: chezmoi state, Homebrew, shell, tmux+TPM, git+signing, SSH agent, pass/GPG, editors, AI tools, key CLIs, `~/bin` wrapper integrity (sem/parallel) + cursor-cli bundled rg, worktrees.

Examples:

```bash
,doctor            # full check
,doctor --quiet    # only warnings/failures
,doctor --verbose  # extra detail (e.g. outdated Homebrew count)
```

### PR readiness audit: `,kbn-pr-audit`

- Source: [`home/exact_bin/executable_,kbn-pr-audit`](../../../home/exact_bin/executable_,kbn-pr-audit)
- Read-only audit of an `elastic/kibana` PR before a reply/resolve/push cycle. It never mutates GitHub (it reports; you act — see the Human-Visible Publication Gate in the AI assistants topic).
- Checks: local `HEAD` vs published PR head alignment, unresolved review threads split human vs bot, deletions disclosed in the body, expected body sections, label consistency (single `release_note:*`, backport target, body↔label agreement), and validation commands recorded in the Test Plan.

```bash
,kbn-pr-audit              # audit the current branch's PR
,kbn-pr-audit 271562       # audit a specific PR number / URL / branch
```

### Run `telegramtui` with optional pass-backed API config: `,tg`

- Source: [`home/exact_bin/executable_,tg`](../../../home/exact_bin/executable_,tg)
- Fork-first runtime:
  - prefers locally built jar from `~/code/telegramtui/main/target/telegramtui-*.jar`
  - falls back to `telegramtui` on `PATH` if no local jar exists
- Setup/install source:
  - `chezmoi` custom-packages installer clones `kapral18/telegramtui` to `~/code/telegramtui/main`
  - tracks `origin/main`, builds with Maven, and installs `~/.local/bin/telegramtui` launcher
  - this install path is personal-profile only (`isWork != true`)
- Optionally reads credentials from:
  - `telegram/apps/tuilegram/app_id`
  - `telegram/apps/tuilegram/api_hash`
- When both pass entries exist, writes `~/.telegramtui/config.properties` (`api.id`/`api.hash`) before launching.
- Runs `telegramtui` by default (or any command passed after `,tg --`).
- Supports repo lifecycle:
  - `,tg --sync` fetch/switch/pull `origin/main`, build, then launch
  - `,tg --build` build only
- Optional overrides:
  - `TELEGRAMTUI_REPO_DIR` (default `~/code/telegramtui/main`)
  - `TELEGRAMTUI_REPO_BRANCH` (default `main`)

Examples:

```bash
,tg                  # runs telegramtui
,tg --sync           # pull fork main, build jar, run
,tg --build          # build local fork jar only
,tg --help           # passes --help to telegramtui
```

### Worktree workflow: `,w`

- Source: [`home/exact_bin/executable_,w`](../../../home/exact_bin/executable_,w)
- Helpers: [`home/exact_bin/utils/,w/`](../../../home/exact_bin/utils/,w/)

Examples:

```bash
,w add feat/my-change main
,w prs 12345
,w issue 12345
,w switch
,w doctor
```

### Transfer patches or files/dirs: `,wh`

- Source: [`home/exact_bin/executable_,wh`](../../../home/exact_bin/executable_,wh)
- Behavior:
  - `,wh post` (no path): writes the current staged diff to `/tmp/staged.patch` and sends it with a one-word Magic Wormhole code.
  - `,wh post <path>`: sends that single file directly, or archives a directory before sending so Wormhole transfers a stable payload. Directory archives include regular files/directories, preserve safe links, and skip non-regular entries such as sockets.
  - `,wh get`: receives the transfer (prompts for the code when omitted) and auto-detects what arrived — a received `*.patch` is applied with `git apply`, a `,wh` directory archive is extracted, and any other file or directory is saved into the destination instead.
- Receive destination (`get -o, --output PATH`): for raw files/dirs it is the target directory (default: current dir); for patches it overrides the patch path (default: `WH_PATCH_FILE`).
- Completions: Fish and Zsh complete `post` / `get`, a path for `post`, and `-o`/`--output` for `get`.
- Optional override: `WH_PATCH_FILE=/path/to/file.patch`

Examples:

```bash
,wh post              # send staged diff
,wh post ./src        # send a directory
,wh post notes.md     # send a single file
,wh get               # receive: apply patch, or save file/dir to cwd
,wh get -o ~/inbox    # save received file/dir into ~/inbox
```

### PR lookup/open: `,gh-prw`

- Source: [`home/exact_bin/executable_,gh-prw`](../../../home/exact_bin/executable_,gh-prw)
- Note: attempts to resolve merged PRs even if the remote branch was deleted.

Examples:

```bash
,gh-prw
,gh-prw --number
,gh-prw --url
```

### Issue lookup/open: `,gh-issuew`

- Source: [`home/exact_bin/executable_,gh-issuew`](../../../home/exact_bin/executable_,gh-issuew)
- Note: infers issue from branch suffix, worktree metadata, or PR body mentions.

Examples:

```bash
,gh-issuew
,gh-issuew --number
,gh-issuew --url
```

### Apply one patch across multiple PRs: `,add-patch-to-prs`

- Source: [`home/exact_bin/executable_,add-patch-to-prs`](../../../home/exact_bin/executable_,add-patch-to-prs)
- Behavior: applies one patch file across selected PRs; if you do not pass PR numbers, it opens an interactive multi-select picker.

Examples:

```bash
,add-patch-to-prs ./fix.patch 12345 12346
,add-patch-to-prs ./fix.patch --search "is:open author:@me"
,add-patch-to-prs ./fix.patch --message "Apply follow-up fix"
```

### Fork + clone + tmux: `,gh-tfork`

- Source: [`home/exact_bin/executable_,gh-tfork`](../../../home/exact_bin/executable_,gh-tfork)
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

- Source: [`home/exact_bin/executable_,pull-rebase`](../../../home/exact_bin/executable_,pull-rebase)
- Behavior: resolves branch upstream and runs `git pull --rebase` with a confirmation prompt.

### Re-converge yarn globals: `,install-yarn-pkgs`

- Source: [`home/exact_bin/executable_,install-yarn-pkgs`](../../../home/exact_bin/executable_,install-yarn-pkgs)
- Input list: `~/.default-yarn-pkgs` (rendered from [`home/readonly_dot_default-yarn-pkgs`](../../../home/readonly_dot_default-yarn-pkgs))
- Behavior: installs missing listed packages, removes globals not on the list, then runs `yarn global upgrade --latest`.

### Apply icon mapping: `,apply-app-icons`

- Source: [`home/exact_bin/executable_,apply-app-icons.tmpl`](../../../home/exact_bin/executable_,apply-app-icons.tmpl)
- Reads mapping/assets from the repo source directory under [`home/app_icons/`](../../../home/app_icons/).

### Run one command across tmux sessions: `,tmux-run-all`

- Source: [`home/exact_bin/executable_,tmux-run-all`](../../../home/exact_bin/executable_,tmux-run-all)

Examples:

```bash
,tmux-run-all "work-*" "git status"
,tmux-run-all --all "work-*" "yarn run test -- --watch=false"
```

### Start/control lowfi in tmux: `,tmux-lowfi`

- Source: [`home/exact_bin/executable_,tmux-lowfi`](../../../home/exact_bin/executable_,tmux-lowfi)

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
| `,gh-worktree`             | Create or reuse local PR/issue worktrees from GitHub repo/number context                                               |
| `,codeowners`              | List matching owners or owned paths from the current repo's CODEOWNERS file                                            |

### Search / discovery helpers

| Command              | Description                                                                                    |
| -------------------- | ---------------------------------------------------------------------------------------------- |
| `,grepo`             | Grep for a pattern across files and open the selected match in `$EDITOR` at the right line     |
| `,search-brew-desc`  | Search installed Homebrew formula descriptions (JSON output)                                   |
| `,fuzzy-brew-search` | Fuzzy search Homebrew descriptions with preview, then drive an "add this to Brewfile" workflow |
| `,search-gh-topic`   | Search GitHub repos by topic with preview, then open the selected repo                         |
| `,youtube-search`    | Search YouTube from an fzf TUI with filters, preview, browser open, and mpv playback           |

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

### AI / Agent helpers

| Command               | Description                                                                           |
| --------------------- | ------------------------------------------------------------------------------------- |
| `,agent-memory`       | Inspect or wipe the selected `/tmp/specs` hook memory topic for the current workspace |
| `,ai-kb`              | Manage the durable local agent knowledge base                                         |
| `,blackboard`         | Manage a run-scoped typed ledger for multi-agent findings and open questions          |
| `,ralph`              | Start, resume, inspect, and control Ralph multi-agent orchestration runs              |
| `,claude-llama-cpp`   | Launch Claude Code against the local llama.cpp-compatible endpoint                    |
| `,codex-llama-cpp`    | Launch Codex against the local llama.cpp-compatible endpoint                          |
| `,opencode-llama-cpp` | Launch OpenCode against the local llama.cpp-compatible endpoint                       |

### Utility helpers

| Command             | Description                                                                                                |
| ------------------- | ---------------------------------------------------------------------------------------------------------- |
| `,cp-files-for-llm` | Copy a directory tree's text contents to the clipboard with file headers, ready to paste into an assistant |
| `,appid`            | Print the macOS bundle identifier for an app name/path                                                     |
| `,dumputi`          | Dump the system's registered Uniform Type Identifiers                                                      |
| `,to-gif`           | Convert a video to an optimized GIF                                                                        |
| `,vid-ipad`         | Re-encode a video for iPad playback                                                                        |
| `,pdf-diff`         | Visual diff two PDFs by compositing pages                                                                  |
| `,nano-banana`      | Generate a Nano Banana (Gemini) image from a text prompt via the Generative Language API                   |
| `,history-sync`     | Merge local Fish history with a 1Password document and push the merged result back (see below)             |
| `,set-default-mic`  | Select the preferred external microphone, falling back to the MacBook microphone                           |
| `,update`           | Reconcile dotfiles plus package-manager update categories                                                  |

#### `,history-sync` details

- Source: [`home/exact_bin/executable_,history-sync`](../../../home/exact_bin/executable_,history-sync)
- Merge logic: [`home/exact_bin/utils/exact_history/executable_fish-history-merge.py`](../../../home/exact_bin/utils/exact_history/executable_fish-history-merge.py)
- Stores the synced history in the 1Password document `fish-history-sync`; that document doubles as an off-machine backup of your fish history.
- The merge is a union keyed by command text, keeping the most recent timestamp per command, and writes entries in chronological order.
- Data-safety behavior:
  - Before replacing local history it writes a snapshot to `~/.local/share/fish/fish_history.bak`.
  - It refuses to install/push a merged result that has fewer entries than the remote copy (guards against parse/merge corruption shrinking the backup).
  - If the remote pull fails but the `fish-history-sync` item exists (transient/auth/network error), it aborts instead of overwriting the good remote with local-only history.
- Caveat: a running fish session keeps its own in-memory history and may rewrite `fish_history` on save. If you restore the file out-of-band, run `history merge` in active fish shells (or restart them) so they adopt it.

### Internal / plumbing helpers

These are used by other scripts, fzf integrations, and Neovim — you rarely invoke them directly:

| Command                  | Description                                                                                    |
| ------------------------ | ---------------------------------------------------------------------------------------------- |
| `,bat-preview`           | Smart preview for fzf (images via chafa, binaries via hexyl, directories via ls, text via bat) |
| `,fzf-git-changed-lines` | Emit changed lines as grep-like entries for fzf                                                |
| `,fzf-preview-follow`    | Center fzf preview around a match line                                                         |
| `,fzf-rg-multiline`      | Convert ripgrep output into NUL-delimited multi-line fzf entries                               |

## Verification And Troubleshooting

Quick checks:

```bash
make verify-bin-surface
command -v ,w
command -v ,gh-prw
command -v ,tmux-run-all
```

If commands are missing after apply, verify:

- [`home/exact_bin/`](../../../home/exact_bin/) contains the source script.
- The script has the `executable_` prefix.
- [`home/dot_config/fish/completions/`](../../../home/dot_config/fish/completions/) contains a matching `readonly_,<name>.fish` completion.
- `make verify-bin-surface` passes, confirming command, completion, docs, and catalog coverage are in sync.
- `chezmoi apply` completed successfully.
- `~/bin` is on `PATH` (`echo "$PATH"`).

## Related

- [Worktree workflow](git-identity/worktrees.md)
- [Apply custom app icons](../macos/custom-app-icons.md)
- [Add a global yarn package](../core/packages/yarn.md)
- [Ralph orchestrator](../ai-assistants/ralph.md) — `,ralph`
- [Agent memory](../ai-assistants/knowledge-base.md) — `,ai-kb`, `,agent-memory`
- [llama.cpp local inference](../ai-assistants/llama-cpp.md) — `,llama-cpp`, `,claude-llama-cpp`
- [Reference map](../../reference/reference-map.md)
