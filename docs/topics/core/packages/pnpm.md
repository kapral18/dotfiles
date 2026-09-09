---
sidebar_position: 15
---

# Add A Global pnpm Package

Global pnpm packages are managed via a plain list. The sync command installs missing packages, removes unmanaged packages, then runs `pnpm update -g --latest` for every unpinned package so installed packages are refreshed instead of staying within the semver range recorded at install time.

## Preconditions

- Node.js and pnpm are installed (both through mise in this setup; `~/.config/mise/config.toml` pins the latest pnpm release for global use).
- `~/.local/share/pnpm/bin` is on `PATH` (the shell configs add it; the installer adds it for itself).
- You verified the package name.

## Steps

Example packages managed this way include `@earendil-works/pi-coding-agent`.

1. Add the package name to:
   - [`home/readonly_dot_default-pnpm-pkgs`](../../../../home/readonly_dot_default-pnpm-pkgs)

   This file is installed as `~/.default-pnpm-pkgs`. `name@x.y.z` pins an exact version; bare names track latest.

2. Apply dotfiles (which triggers the hook):

   ```bash
   chezmoi apply
   ```

Or run the installer command directly:

- [`home/exact_bin/executable_,install-pnpm-pkgs`](../../../../home/exact_bin/executable_,install-pnpm-pkgs)

## Verification

```bash
pnpm ls -g --depth 0 | rg '<package-name>'
```

## What It Does

The installer reads `~/.default-pnpm-pkgs`, compares it with `pnpm ls -g --json`, installs missing packages (`pnpm add -g`), re-pins packages whose installed version differs from an exact pin, uninstalls global packages not on the list (`pnpm remove -g`), then runs `pnpm update -g --latest` for each unpinned package.

pnpm 11+ installs every global package into its own hashed project directory under `~/.local/share/pnpm/global/v11/`, and that directory moves on every add or update. Consumers that need a stable module path (Pi's `packages` setting loads `pi-mcp-adapter` and `pi-subagents` by path) read `~/.local/share/pnpm-global-links/node_modules/<package>` instead; the installer rebuilds that symlink tree after every sync.

Package operations pass `--yes` and disconnect stdin so pnpm does not prompt during a chezmoi run, including when launched from a terminal. Unapproved dependency build scripts remain ignored.

If a package operation fails, the installer prints pnpm's error and stops with a nonzero exit status. It refreshes links from the installed state even after a partial sync. If that state cannot be read or parsed, it preserves the existing link tree and reports the failure.

## Rollback / Undo

1. Remove the package from [`home/readonly_dot_default-pnpm-pkgs`](../../../../home/readonly_dot_default-pnpm-pkgs).
2. Re-apply:

```bash
chezmoi apply
```

_(The package will be automatically uninstalled because it is no longer in the desired list)._
