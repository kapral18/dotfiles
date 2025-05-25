# Dotfiles Repository

This repository manages my personal configuration files across various tools and environments using [Chezmoi](https://www.chezmoi.io/). It aims to provide a consistent and reproducible setup for my development environment.

## Table of Contents

- [Overview](#overview)
- [Managed Configurations](#managed-configurations)
- [Manual Setup](#manual-setup)
- [Usage](#usage)
- [10 feet view](#10-feet-view)
- [Contributing](#contributing)
- [License](#license)

## Overview

This repository contains configuration files for various tools and environments, including shell configurations, text editors, terminal emulators, and more. The configurations are managed using Chezmoi, a tool that allows for easy management of dotfiles across different machines.

The repository is structured to be easily maintainable and extensible. It includes configurations for both personal and work environments, with conditional logic to apply specific settings based on the environment.

## Managed Configurations

The repository manages configurations for the following tools and environments:

- **1Password:** 1Password CLI configuration.
- **Alfred:** Alfred configuration for productivity.
- **ASDF:** ASDF version manager configuration.
- **Bartender:** Bartender configuration for managing menu bar items.
- **Bash:** Bash shell configuration, including aliases and environment variables and custom functions.
- **Bat:** Bat configuration for syntax highlighting.
- **Chezmoi:** Configuration for managing dotfiles.
- **Curl:** Curl configuration.
- **Fish:** Fish shell configuration, including aliases, environment variables and custom functions.
- **GitHub CLI:** GitHub CLI configuration.
- **Git:** Global git configuration, including aliases and settings.
- **GnuPG:** GnuPG configuration for encryption and signing.
- **Ghostty:** Ghostty terminal emulator configuration.
- **HammerSpoon:** HammerSpoon configuration for window management.
- **HomeBrew:** Homebrew package manager configuration.
- **Karabiner:** Karabiner-Elements configuration for keyboard customization.
- **Kitty:** Kitty terminal emulator configuration.
- **NeoVim:** Neovim configuration, including plugins, keymaps, and settings.
- **Rectangle:** Rectangle window manager configuration.
- **SSH:** SSH configuration, including keys and known hosts.
- **Starship:** Starship prompt configuration.
- **Tmux:** Tmux configuration, including plugins, keymaps, and settings.
- **Topgrade:** Topgrade configuration for system updates.
- **Wezterm:** Wezterm terminal emulator configuration.
- **Zsh:** Zsh shell configuration, including aliases, environment variables and custom functions.
- **iTerm2:** iTerm2 terminal emulator configuration.
- **LazyGit:** lazygit configuration.
- **macOS:** macOS system configurations, including defaults and settings.

## Manual Setup

Before using this repository, you need to perform the following manual steps:

1. **Install and set up 1Password:** Ensure that 1Password is installed and configured on your system. This is required for managing SSH keys and other secrets.
2. **Initialize Chezmoi:** Run the following command to initialize Chezmoi and apply the configurations:

   ```bash
   sh -c "$(curl -fsLS get.chezmoi.io/lb)" -- init --apply kapral18
   ```

   This command will download and install Chezmoi, initialize the repository, and apply the configurations.

## Usage

After completing the manual setup, you can use Chezmoi to manage your dotfiles. Here are some common commands:

- `chezmoi add <file>`: Add a new file to be managed by Chezmoi.
- `chezmoi apply`: Apply the configurations to your system.
- `chezmoi diff`: Show the differences between your local files and the managed configurations.
- `chezmoi edit <file>`: Edit a managed file.
- `chezmoi forget <file>`: Remove a file from Chezmoi management.
- `chezmoi update`: Update the repository with the latest changes.

For more information on using Chezmoi, refer to the [official documentation](https://www.chezmoi.io/).

## Contributing

Contributions to this repository are welcome. If you have any improvements or suggestions, please feel free to submit a pull request.

## License

This repository is licensed under the [MIT License](LICENSE).
