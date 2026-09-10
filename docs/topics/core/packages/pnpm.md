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

## Release-Age Quarantine

pnpm 11+ ships a built-in `minimumReleaseAge` of 1440 minutes: `pnpm update -g --latest` and `pnpm outdated -g` silently skip any version published less than a day ago, so `,update` can report success while `omp update` (which reads the `latest` dist-tag directly) already sees a newer release.

[`home/dot_config/pnpm/readonly_config.yaml.tmpl`](../../../../home/dot_config/pnpm/readonly_config.yaml.tmpl) renders `~/.config/pnpm/config.yaml` with `minimumReleaseAgeExclude` covering every package in `~/.default-pnpm-pkgs` (pins reduce to the bare name), so listed packages update as soon as they publish. Scoped packages are listed as `@scope/*`, not by exact name: pnpm's non-strict default auto-approves same-day transitive versions into the global project's own `pnpm-workspace.yaml`, and that project list replaces the global one, which would re-quarantine the top-level package on the next sync. Same-scope companions (for example the 17 `@oh-my-pi/*` packages behind `omp`) are the case that triggers this on every release, so the scope glob keeps the global list in effect. Unscoped packages keep exact names, so a same-day third-party transitive release can still trigger that write. The 05 hook hashes the config template, so changing exclusions re-runs the sync.

Check the effective list with:

```bash
pnpm config get --global minimum-release-age-exclude
```

## Rollback / Undo

1. Remove the package from [`home/readonly_dot_default-pnpm-pkgs`](../../../../home/readonly_dot_default-pnpm-pkgs).
2. Re-apply:

```bash
chezmoi apply
```

_(The package will be automatically uninstalled because it is no longer in the desired list)._
