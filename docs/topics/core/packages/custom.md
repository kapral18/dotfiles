---
sidebar_position: 17
---

# Custom Packages Registry

"Custom packages" are tools/apps installed outside standard package managers using a managed chezmoi list. This registry supports GitHub-release assets.

## Preconditions

- The tool/app is not available in higher-priority package managers for this repo, or the higher-priority package is known to be unsafe for this app's update model.
- For GitHub-release formats, you identified the official GitHub repository and release asset naming.
- You know which format applies: `dmg`, `file`, `tar_gz_bin`, or `zip_opt`.

## Where The List Lives

- [`home/readonly_dot_default-custom-packages.tmpl`](../../../../home/readonly_dot_default-custom-packages.tmpl)

## Supported Formats

The list is pipe-delimited. The template itself documents the schema:

- DMG apps: `dmg|App Name|owner/repo|release-tag|AppBundle.app|asset-pattern`
- Single binaries: `file|tool-name|owner/repo|release-tag|asset-pattern|output-binary-name`
- Tarballs with a binary: `tar_gz_bin|tool-name|owner/repo|release-tag|asset-pattern|bin-in-archive|output-binary-name`
- Zip bundles that must keep sibling dylibs: `zip_opt|tool-name|owner/repo|release-tag|asset-pattern|bin-in-archive|output-binary-name`

## Steps

1. Add or edit the package row in:

- [`home/readonly_dot_default-custom-packages.tmpl`](../../../../home/readonly_dot_default-custom-packages.tmpl)

1. Apply:

```bash
chezmoi apply
```

The installer is:

- [`home/.chezmoiscripts/run_onchange_after_05-install-custom-packages.sh.tmpl`](../../../../home/.chezmoiscripts/run_onchange_after_05-install-custom-packages.sh.tmpl)

It installs binaries into `$HOME/.local/bin` and DMG apps into `/Applications`. `zip_opt` also extracts the zip into `$HOME/.local/opt/<tool-name>/` and writes a PATH wrapper so sibling dylibs resolve.

The installer script embeds a hash of the custom packages list so `chezmoi apply` re-runs it when you add or change rows in the list (not only when the installer script itself changes).

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

## Delete / Undo

1. Remove the row from [`home/readonly_dot_default-custom-packages.tmpl`](../../../../home/readonly_dot_default-custom-packages.tmpl).
2. Re-apply:

```bash
chezmoi apply
```

1. If needed, manually remove residual app/binary:

- `/Applications/<AppName>.app`
- `$HOME/.local/bin/<binary-name>`
- `$HOME/.local/opt/<tool-name>/` (for `zip_opt`)
