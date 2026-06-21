---
sidebar_position: 1
---

# High-leverage commands

These are the commands most likely to change how you work day to day.

## System health: `,doctor`

- Source: [`home/exact_bin/executable_,doctor`](../../../../home/exact_bin/executable_,doctor)
- Checks: chezmoi state, Homebrew, shell, tmux+TPM, git+signing, SSH agent, pass/GPG, editors, AI tools, key CLIs, `~/bin` wrapper integrity, cursor-cli bundled `rg`, and worktrees.

```bash
,doctor
,doctor --quiet
,doctor --verbose
```

## PR readiness: `,kbn-pr-audit`

- Source: [`home/exact_bin/executable_,kbn-pr-audit`](../../../../home/exact_bin/executable_,kbn-pr-audit)
- Scope: read-only audit of an `elastic/kibana` PR before a reply/resolve/push cycle.
- Checks: local `HEAD` vs PR head, unresolved review threads split human vs bot, deletions disclosed in the body, expected body sections, label consistency, backport target consistency, and Test Plan validation commands.

```bash
,kbn-pr-audit
,kbn-pr-audit 271562
```

## Worktrees: `,w`

- Source: [`home/exact_bin/executable_,w`](../../../../home/exact_bin/executable_,w)
- Helpers: [`home/exact_bin/utils/,w/`](../../../../home/exact_bin/utils/,w/)

```bash
,w add feat/my-change main
,w prs 12345
,w issue 12345
,w switch
,w doctor
```

For the full workflow, see [Git worktrees](../git-identity/worktrees.md).

## GitHub lookup and bootstrap

| Command        | Purpose                                                                  |
| -------------- | ------------------------------------------------------------------------ |
| `,gh-prw`      | Resolve/open the current branch's PR; can print number or URL            |
| `,gh-issuew`   | Resolve/open the issue from branch suffix, worktree metadata, or PR body |
| `,gh-worktree` | Create or reuse local PR/issue worktrees from GitHub context             |
| `,gh-tfork`    | Fork/clone a repo and create a tmux session                              |

Sources live under [`home/exact_bin/`](../../../../home/exact_bin/).

```bash
,gh-prw --url
,gh-issuew --number
,gh-tfork elastic/integrations
```

`,gh-tfork` clones to `~/work/<repo>/<default-branch>` for `elastic/*` and `~/code/<repo>/<default-branch>` otherwise. For `elastic/kibana`, it uses date-anchored shallow history (`--shallow-since=2022-01-01 --no-tags`).

## Patch and file transfer: `,wh`

- Source: [`home/exact_bin/executable_,wh`](../../../../home/exact_bin/executable_,wh)
- `,wh post` writes the current staged diff to `/tmp/staged.patch` and sends it with Magic Wormhole.
- `,wh post <path>` sends a single file or archives a directory first.
- `,wh get` receives and auto-detects: apply patch, extract archive, or save file/dir.
- Fish and Zsh completions cover `post`, `get`, path arguments, and `-o/--output`.

```bash
,wh post
,wh post ./src
,wh post notes.md
,wh get
,wh get -o ~/inbox
```

## Multi-PR patching: `,add-patch-to-prs`

- Source: [`home/exact_bin/executable_,add-patch-to-prs`](../../../../home/exact_bin/executable_,add-patch-to-prs)
- Applies one patch file across selected PRs.
- Opens an interactive multi-select picker when PR numbers are omitted.

```bash
,add-patch-to-prs ./fix.patch 12345 12346
,add-patch-to-prs ./fix.patch --search "is:open author:@me"
,add-patch-to-prs ./fix.patch --message "Apply follow-up fix"
```

## Telegram TUI launcher: `,tg`

- Source: [`home/exact_bin/executable_,tg`](../../../../home/exact_bin/executable_,tg)
- Prefers a locally built jar from `~/code/telegramtui/main/target/telegramtui-*.jar`.
- Falls back to `telegramtui` on `PATH`.
- Optionally writes `~/.telegramtui/config.properties` from pass entries `telegram/apps/tuilegram/app_id` and `telegram/apps/tuilegram/api_hash`.

```bash
,tg
,tg --sync
,tg --build
,tg --help
```

## Package and icon reconverge helpers

| Command              | Purpose                                                                          |
| -------------------- | -------------------------------------------------------------------------------- |
| `,pull-rebase`       | Resolve branch upstream and run `git pull --rebase` behind a confirmation prompt |
| `,install-yarn-pkgs` | Reconcile global Yarn packages against `~/.default-yarn-pkgs`                    |
| `,apply-app-icons`   | Apply app icon mappings from `home/app_icons/`                                   |

## tmux helpers

| Command         | Purpose                                         |
| --------------- | ----------------------------------------------- |
| `,tmux-run-all` | Run one command across matching tmux sessions   |
| `,tmux-lowfi`   | Start/control lowfi in a dedicated tmux session |

```bash
,tmux-run-all "work-*" "git status"
,tmux-run-all --all "work-*" "yarn run test -- --watch=false"
,tmux-lowfi p
,tmux-lowfi nt
,tmux-lowfi q
```
