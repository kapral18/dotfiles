# Lowfi In tmux

Back: [`docs/recipes/index.md`](index.md)

If you like background music while coding, this repo includes a small helper
that runs `lowfi` inside a tmux session.

## Preconditions

- `tmux` is installed and running.
- `lowfi` is installed.
- Tracklists exist under `~/Library/Application Support/lowfi`.

## Command

- `,tmux-lowfi`

Source:

- `home/exact_bin/executable_,tmux-lowfi`

## Steps

Play/pause:

```bash
,tmux-lowfi p
```

Skip:

```bash
,tmux-lowfi s
```

Next tracklist:

```bash
,tmux-lowfi nt
```

Quit (kills the tmux session):

```bash
,tmux-lowfi q
```

## Verification

```bash
tmux has-session -t lowfi
```

Expected:

- Exit `0` when the session is running.
- Exit non-zero after `,tmux-lowfi q`.

## Rollback / Undo

- Stop and remove session:

```bash
,tmux-lowfi q
```

- Remove current tracklist state file if needed:

```bash
rm -f /tmp/tmux-lowfi-current-tracklist
```

## Where Tracklists Come From

Tracklists live under:

- `~/Library/Application Support/lowfi`

They are pulled via `chezmoi` externals:

- `home/.chezmoiexternal.toml`
