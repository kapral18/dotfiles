---
sidebar_position: 2
---

# Custom Packages Registry

"Custom packages" are tools/apps installed outside standard package managers using a managed chezmoi list. This registry supports both GitHub-release assets and source-based builds.

## Preconditions

- The tool/app is not available in higher-priority package managers for this repo.
- You identified the official GitHub repository and release asset naming.
- You know which format applies: `dmg`, `file`, `tar_gz_bin`, or `git_maven_jar`.

## Where The List Lives

- [`home/readonly_dot_default-custom-packages.tmpl`](../../../../home/readonly_dot_default-custom-packages.tmpl)

## Supported Formats

The list is pipe-delimited. The template itself documents the schema:

- DMG apps: `dmg|App Name|owner/repo|release-tag|AppBundle.app|asset-pattern`
- Single binaries: `file|tool-name|owner/repo|release-tag|asset-pattern|output-binary-name`
- Tarballs with a binary: `tar_gz_bin|tool-name|owner/repo|release-tag|asset-pattern|bin-in-archive|output-binary-name`
- Source build (Git + Maven jar): `git_maven_jar|tool-name|owner/repo|branch|output-binary-name`

## Steps

1. Add or edit the package row in:

- [`home/readonly_dot_default-custom-packages.tmpl`](../../../../home/readonly_dot_default-custom-packages.tmpl)

1. Apply:

```bash
chezmoi apply
```

The installer is:

- [`home/.chezmoiscripts/run_onchange_after_05-install-custom-packages.sh.tmpl`](../../../../home/.chezmoiscripts/run_onchange_after_05-install-custom-packages.sh.tmpl)

It installs binaries into `$HOME/.local/bin` and DMG apps into `/Applications`. For `git_maven_jar`, it clones into `~/code/<repo>/<branch>`, builds, and installs a launcher binary.

The installer script embeds a hash of the custom packages list so `chezmoi apply` re-runs it when you add or change rows in the list (not only when the installer script itself changes).

For `git_maven_jar`, CRUD is declarative:

- create/update row -> clone/pull/build/install
- remove row -> auto-remove stale launcher, and auto-remove stale repo directory if it is clean
- dirty stale repos are preserved with a warning (to avoid data loss)

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

For source builds (`git_maven_jar`), stale repo cleanup is automatic when clean. If local changes exist in the stale repo, cleanup is skipped and you can remove it manually.
