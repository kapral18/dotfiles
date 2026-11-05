---
sidebar_position: 8
---

# Lowfi in herdr

`,herdr-lowfi` runs `lowfi` in a dedicated herdr workspace labelled `lowfi`.

## Preconditions

- herdr is running.
- `lowfi` is installed.
- Tracklists exist under `~/Library/Application Support/lowfi`, pulled by chezmoi externals ([`home/.chezmoiexternal.toml`](../../../../home/.chezmoiexternal.toml)).

## Command

Source: [`home/exact_bin/executable_,herdr-lowfi`](../../../../home/exact_bin/executable_,herdr-lowfi)

| Key   | Command           | Action                                     |
| ----- | ----------------- | ------------------------------------------ |
| `F10` | `,herdr-lowfi p`  | Play/pause (starts lowfi when not running) |
| `F11` | `,herdr-lowfi s`  | Skip                                       |
| `F12` | `,herdr-lowfi nt` | Restart with the next tracklist            |
| —     | `,herdr-lowfi q`  | Close the `lowfi` workspace                |

The current tracklist is remembered in `/tmp/herdr-lowfi-current-tracklist`.

## Verification

```bash
herdr workspace list | jq -r '.result.workspaces[].label' | grep -x lowfi
```
