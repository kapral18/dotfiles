# Dotfiles Repository

This repository manages my personal configuration files across various tools and environments using [Chezmoi](https://www.chezmoi.io/). It aims to provide a consistent and reproducible setup for my development environment.

## Table of Contents

- [Overview](#overview)
- [Managed Configurations](#managed-configurations)
- [Manual Setup](#manual-setup)
- [Repository Structure](#repository-structure)
- [Usage](#usage)
- [Contributing](#contributing)
- [License](#license)

## Overview

This repository contains configuration files for various tools and environments, including shell configurations, text editors, terminal emulators, and more. The configurations are managed using Chezmoi, a tool that allows for easy management of dotfiles across different machines.

The repository is structured to be easily maintainable and extensible. It includes configurations for both personal and work environments, with conditional logic to apply specific settings based on the environment.

## Managed Configurations

The repository manages configurations for the following tools and environments:

- **Bash:** Bash shell configuration, including aliases and environment variables and custom functions.
- **Bat:** Bat configuration for syntax highlighting.
- **Chezmoi:** Configuration for managing dotfiles.
- **Conda:** Conda environment configuration.
- **Curl:** Curl configuration.
- **Fish:** Fish shell configuration, including aliases, environment variables and custom functions.
- **Git:** Global git configuration, including aliases and settings.
- **GnuPG:** GnuPG configuration for encryption and signing.
- **Homebrew:** Homebrew package manager configuration.
- **Karabiner:** Karabiner-Elements configuration for keyboard customization.
- **Kitty:** Kitty terminal emulator configuration.
- **Neovim:** Neovim configuration, including plugins, keymaps, and settings.
- **Node.js:** Node Version Manager configuration.
- **Python:** Python version and environment configuration.
- **Ruby:** Ruby version configuration.
- **SSH:** SSH configuration, including keys and known hosts.
- **Starship:** Starship prompt configuration.
- **Tmux:** Tmux configuration, including plugins, keymaps, and settings.
- **Topgrade:** Topgrade configuration for system updates.
- **Wezterm:** Wezterm terminal emulator configuration.
- **Zsh:** Zsh shell configuration, including aliases, environment variables and custom functions.
- **bat:** bat configuration.
- **gh:** GitHub CLI configuration.
- **iTerm2:** iTerm2 terminal emulator configuration.
- **lazygit:** lazygit configuration.
- **macOS:** macOS system configurations, including defaults and settings.
- **newsboat:** newsboat configuration.

## Manual Setup

Before using this repository, you need to perform the following manual steps:

1. **Install and set up 1Password:** Ensure that 1Password is installed and configured on your system. This is required for managing SSH keys and other secrets.
2. **Initialize Chezmoi:** Run the following command to initialize Chezmoi and apply the configurations:

   ```bash
   sh -c "$(curl -fsLS get.chezmoi.io/lb)" -- init --apply kapral18
   ```

   This command will download and install Chezmoi, initialize the repository, and apply the configurations.

## Repository Structure

The repository is organized as follows:

- `home/`: Contains all the configuration files that will be placed in the user's home directory.
  - `.chezmoiexternals/`: Contains external git repositories managed by Chezmoi.
  - `.chezmoiscripts/`: Contains scripts that are executed by Chezmoi during the apply process.
  - `.chezmoitemplates/`: Contains templates used by Chezmoi to generate configuration files.
  - `.plists/`: Contains plist files for macOS applications.
  - `bin/`: Contains executable scripts.
  - `dot_config/`: Contains configuration files for various tools.
    - `chatblade/`: Configuration for chatblade.
    - `exact_1Password/`: Configuration for 1Password.
    - `exact_bat/`: Configuration for bat.
    - `exact_kitty/`: Configuration for kitty.
    - `exact_newsboat/`: Configuration for newsboat.
    - `exact_nvim/`: Configuration for Neovim.
    - `exact_wezterm/`: Configuration for Wezterm.
    - `gh/`: Configuration for GitHub CLI.
    - `iterm2/`: Configuration for iTerm2.
    - `lazygit/`: Configuration for lazygit.
    - `private_fish/`: Configuration for Fish shell.
    - `private_karabiner/`: Configuration for Karabiner-Elements.
    - `tmux/`: Configuration for Tmux.
  - `dot_ssh/`: Contains SSH configuration files.
  - `exact_dot_conda/`: Contains Conda configuration files.
  - `private_dot_gnupg/`: Contains GnuPG configuration files.
  - `work/`: Contains work-specific configuration files.
  - `.chezmoi.toml.tmpl`: Template for Chezmoi configuration.
  - `.chezmoiignore`: Files to ignore by Chezmoi.
  - `.osx.core`: Core macOS settings.
  - `.osx.extra`: Extra macOS settings.
  - `dot_bashrc.tmpl`: Template for Bash configuration.
  - `dot_condarc`: Conda configuration.
  - `dot_curlrc`: Curl configuration.
  - `dot_gitignore`: Git ignore configuration.
  - `dot_inputrc`: Input configuration.
  - `dot_nvmrc`: Node Version Manager configuration.
  - `dot_python-version`: Python version configuration.
  - `dot_ruby-version`: Ruby version configuration.
  - `dot_zshrc.tmpl`: Template for Zsh configuration.
  - `private_dot_gitconfig.tmpl`: Template for Git configuration.
- `.chezmoiroot`: Specifies the root directory for Chezmoi.
- `README.md`: This file.

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
