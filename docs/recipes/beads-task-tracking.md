# Beads Task Tracking

Back: [`docs/recipes/index.md`](index.md)

This setup includes an opinionated way to use Beads (`bd`) without a global
daemon and without mixing data across unrelated repos.

## Preconditions

- `bd` CLI is installed and on `PATH`.
- You are inside a git repository (recommended for stable repo naming).

## The Wrapper

`bdlocal` is defined in:

- `home/dot_config/fish/config.fish.tmpl`

It resolves a per-repo `$BEADS_DIR` under `~/beads-data/<repo>` and pins the DB
to:

- `$BEADS_DIR/.beads/beads.db`

Then it runs:

- `bd --db ... --no-auto-flush --no-auto-import --no-daemon`

## Steps

From inside any git repo:

```bash
bdlocal status
```

If you `cd` into another repo, the DB location changes automatically.

## Verification

```bash
echo "$BEADS_DIR"
bdlocal status
```

Confirm that `BEADS_DIR` changes as you move between repositories.

## Rollback / Undo

- Stop using wrapper in current shell:
  - run `bd ...` directly instead of `bdlocal`.
- Remove local repo data directory (only if you want to delete local Beads data):

```bash
rm -rf "$BEADS_DIR"
```

## Why This Exists

For people used to Jira/Linear/etc., Beads is a lightweight local alternative.
The key benefit of this wrapper is that it keeps data scoped per-repo.
