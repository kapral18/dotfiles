---
sidebar_position: 7
---

# Add A Global yarn Package

Global yarn packages are managed via a plain list. The sync command installs missing packages, removes unmanaged packages, then runs `yarn global upgrade --latest` so installed packages are refreshed instead of staying within the old semver range recorded by Yarn.

## Preconditions

- Node.js/yarn are installed (through ASDF in this setup).
- You verified the package name.

## Steps

Example packages managed this way include `@earendil-works/pi-coding-agent`.

1. Add the package name to:
   - [`home/readonly_dot_default-yarn-pkgs`](../../../../home/readonly_dot_default-yarn-pkgs)

   This file is installed as `~/.default-yarn-pkgs`.

2. Apply dotfiles (which triggers the hook):

   ```bash
   chezmoi apply
   ```

Or run the installer command directly:

- [`home/exact_bin/executable_,install-yarn-pkgs`](../../../../home/exact_bin/executable_,install-yarn-pkgs)

## Verification

```bash
yarn global list | rg '<package-name>'
```

## What It Does

The installer reads `~/.default-yarn-pkgs`, installs missing packages, uninstalls global packages not on the list, then runs `yarn global upgrade --latest`. This avoids Yarn v1 staying inside an old `0.x` range such as `^0.74.0` when a package has moved to `0.75.x`.

## Rollback / Undo

1. Remove the package from [`home/readonly_dot_default-yarn-pkgs`](../../../../home/readonly_dot_default-yarn-pkgs).
2. Re-apply:

```bash
chezmoi apply
```

_(The package will be automatically uninstalled because it is no longer in the desired list)._
