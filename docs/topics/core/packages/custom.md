---
sidebar_position: 17
---

# Custom Packages Registry

"Custom packages" are tools/apps installed outside standard package managers using a managed chezmoi list. This registry supports GitHub-release assets and direct HTTPS DMGs.

## Preconditions

- The tool/app is not available in higher-priority package managers for this repo, or the higher-priority package is known to be unsafe for this app's update model.
- For GitHub-release formats, you identified the official GitHub repository and release asset naming.
- For direct DMGs, you verified the HTTPS download URL on the publisher's site and inspected the app bundle.
- You know which format applies: `dmg`, `file`, `tar_gz_bin`, or `zip_opt`.

## Where The List Lives

- [`home/readonly_dot_default-custom-packages.tmpl`](../../../../home/readonly_dot_default-custom-packages.tmpl)

## Supported Formats

The list is pipe-delimited. The template itself documents the schema:

- GitHub DMG apps: `dmg|App Name|owner/repo|release-tag|AppBundle.app|asset-pattern`
- Direct DMG apps: `dmg|App Name|https://.../app.dmg|latest|AppBundle.app|.dmg`
- Single binaries: `file|tool-name|owner/repo|release-tag|asset-pattern|output-binary-name`
- Tarballs with a binary: `tar_gz_bin|tool-name|owner/repo|release-tag|asset-pattern|bin-in-archive|output-binary-name`
- Zip bundles that must keep sibling dylibs: `zip_opt|tool-name|owner/repo|release-tag|asset-pattern|bin-in-archive|output-binary-name`

Direct DMGs use `latest` as a placeholder and `.dmg` as the asset pattern. Existing app directories are skipped, not upgraded.

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

`file` and `tar_gz_bin` rows keep a record in `$HOME/.local/state/custom-packages/<output-binary-name>.release` with the resolved tag, repo, asset pattern, and archive member. A later run skips the row when the binary exists and the record matches; `latest` resolves to the current tag first, and a changed asset pattern or archive member (for example switching arch) reinstalls. The installer never runs a binary to read its version. `zip_opt` keeps its tag in `$HOME/.local/opt/<tool-name>/.release-tag`.

The installer script embeds a hash of the custom packages list so `chezmoi apply` re-runs it when you add or change rows in the list (not only when the installer script itself changes).

## Verification

For `file` and `tar_gz_bin` tools:

```bash
command -v <binary-name>
cat "$HOME/.local/state/custom-packages/<binary-name>.release"
```

For `zip_opt` tools:

```bash
command -v <binary-name>
cat "$HOME/.local/opt/<tool-name>/.release-tag"
```

The record shows what the installer wrote, not that the binary runs. Run the tool once by hand, with a flag its `--help` lists, to confirm it starts.

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
- `$HOME/.local/bin/<binary-name>` and `$HOME/.local/state/custom-packages/<binary-name>.release`
- `$HOME/.local/opt/<tool-name>/` (for `zip_opt`)
