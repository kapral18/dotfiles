# Dotfiles

### Configs

- chezmoi
- git
- bash
- fish
- nvim
- tmux
- alacritty
- wezterm
- starship
- conda
- curl
- python
- ruby
- karabiner
- topgrade

# Manual part

- setup export /opt/homebrew/bin in both zshrc and bashrc
- Download hombrew
- brew install google-drive 1password cryptomator pass
- git clone .password-store
- gpg import .pgp/public and .pgp/private
- gpg trust
- sh -c "$(curl -fsLS get.chezmoi.io/lb)" -- init --apply git@github.com:kapral18/dotfiles.git
