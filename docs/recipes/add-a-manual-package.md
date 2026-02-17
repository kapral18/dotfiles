# Add A Manual Package

Back: [`docs/recipes/index.md`](index.md)

"Manual packages" are tools/apps installed from GitHub releases (including DMG
apps) using a managed list.

## Preconditions

- The tool/app is not available in higher-priority package managers for this repo.
- You identified the official GitHub repository and release asset naming.
- You know which format applies: `dmg`, `file`, or `tar_gz_bin`.

## Where The List Lives

- `home/readonly_dot_default-manual-packages.tmpl`

## Supported Formats

The list is pipe-delimited. The template itself documents the schema:

- DMG apps: `dmg|App Name|owner/repo|release-tag|AppBundle.app|asset-pattern`
- Single binaries: `file|tool-name|owner/repo|release-tag|asset-pattern|output-binary-name`
- Tarballs with a binary: `tar_gz_bin|tool-name|owner/repo|release-tag|asset-pattern|bin-in-archive|output-binary-name`

## Steps

1. Add or edit the package row in:

- `home/readonly_dot_default-manual-packages.tmpl`

2. Apply:

```bash
chezmoi apply
```

The installer is:

- `home/.chezmoiscripts/run_onchange_after_05-install-manual-packages.sh.tmpl`

It installs binaries into `$HOME/.local/bin` and DMG apps into `/Applications`.

## Verification

For CLI tools:

```bash
command -v <binary-name>
<binary-name> --version
```

For DMG apps:

```bash
ls -d "/Applications/<AppName>.app"
```

## Rollback / Undo

1. Remove the row from `home/readonly_dot_default-manual-packages.tmpl`.
2. Re-apply:

```bash
chezmoi apply
```

3. Manually remove residual app/binary if needed:
- `/Applications/<AppName>.app`
- `$HOME/.local/bin/<binary-name>`
