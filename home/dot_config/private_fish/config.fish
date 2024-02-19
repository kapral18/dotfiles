# FISH
set fish_greeting

# Lang
set -gx LC_ALL en_US.UTF-8
set -gx LANG en_US.UTF-8

# No homebrew auto update during brew install
set -gx HOMEBREW_NO_AUTO_UPDATE 1

# My terminal editor is always Vim by default
set -x EDITOR nvim
set -x VISUAL nvim

# Set terminal colors to 256
set -gx TERM xterm-256color

# XDG is used by lazygit and other tools
set -gx XDG_CONFIG_HOME "$HOME/.config"

# System
set -gx XDG_DATA_DIRS /usr/share /usr/local/share
set -gx XDG_CONFIG_DIRS /etc/xdg

# User
set -gx XDG_CONFIG_HOME $HOME/.config
set -gx XDG_CACHE_HOME $HOME/.cache
set -gx XDG_DATA_HOME $HOME/.local/share
set -gx XDG_DESKTOP_DIR $HOME/Desktop
set -gx XDG_DOCUMENTS_DIR $HOME/Documents
set -gx XDG_DOWNLOAD_DIR $HOME/Downloads
set -gx XDG_MUSIC_DIR $HOME/Music
set -gx XDG_PICTURES_DIR $HOME/Pictures
set -gx XDG_VIDEOS_DIR $HOME/Videos

# nvm
set -gx nvm_default_version lts

# Go
set -gx GOPATH $HOME/go


# Chatblade
set -gx OPENAI_API_MODEL 4t

# Docker
set -gx DOCKER_HIDE_LEGACY_COMMANDS true

# PyEnv
set -gx PYENV_ROOT $HOME/.pyenv

# Rbenv
set -gx RBENV_ROOT $HOME/.rbenv

# FZF
set FD_OPTIONS "--hidden --follow"
set -gx FZF_DEFAULT_OPTS "--no-mouse --height 80% --reverse --multi --info=inline --preview='bat {} --color always' --preview-window='right:60%:wrap' --bind=ctrl-d:half-page-down,ctrl-u:half-page-up,ctrl-b:page-up,ctrl-f:page-down"
set -gx FZF_DEFAULT_COMMAND "git ls-files --cached --others --exclude-standard 2>/dev/null || fd --type f --type l $FD_OPTIONS"
set -gx FZF_CTRL_T_COMMAND "$FZF_DEFAULT_COMMAND"
set -gx FZF_ALT_C_COMMAND "fd --type d $FD_OPTIONS"

# Brew 
set -gx HOMEBREW_PREFIX /opt/homebrew
set -gx HOMEBREW_CELLAR /opt/homebrew/Cellar
set -gx HOMEBREW_REPOSITORY /opt/homebrew
set -gx MANPATH /opt/homebrew/share/man $MANPATH
set -gx INFOPATH /opt/homebrew/share/info $INFOPATH

# Paths
fish_add_path /opt/homebrew/bin
fish_add_path /opt/homebrew/sbin

fish_add_path $RBENV_ROOT/bin
fish_add_path $PYENV_ROOT/bin
fish_add_path $GOPATH/bin
fish_add_path $HOME/.cargo/bin
fish_add_path $HOME/.local/bin
fish_add_path $HOME/bin

# Inits
rbenv init - | source
pyenv init - | source
starship init fish | source
zoxide init fish | source
fnm env --use-on-cd | source

# >>> conda initialize >>>
# !! Contents within this block are managed by 'conda init' !!
if test -f /opt/homebrew/Caskroom/miniconda/base/bin/conda
    eval /opt/homebrew/Caskroom/miniconda/base/bin/conda "shell.fish" hook $argv | source
else
    if test -f "/opt/homebrew/Caskroom/miniconda/base/etc/fish/conf.d/conda.fish"
        . "/opt/homebrew/Caskroom/miniconda/base/etc/fish/conf.d/conda.fish"
    else
        set -x PATH /opt/homebrew/Caskroom/miniconda/base/bin $PATH
    end
end
# <<< conda initialize <<<

# Aliases
alias g="git"
alias tree='tree -I ".git|node_modules"'
alias t="tmux"
alias v=nvim
alias c=chezmoi
alias fzfi='git ls-files --cached --others --exclude-standard 2>/dev/null || fd --type f --type l $FD_OPTIONS'
alias ghs='gh copilot suggest'
alias ghx='gh copilot explain'
alias nvm='fnm'

if hash lsd 2>/dev/null
    alias ls='lsd -A'
    alias l='lsd -lAh'
    alias ll='lsd -lAtrh'
    alias la='lsd -A'
else
    alias ls='ls -A'
    alias l='ls -lAh'
    alias ll='ls -lAtrh'
    alias la='ls -A'
end

# function that wraps brew
# and adds brew bundle dump --file=~/.local/share/chezmoi/home/.Brewfile
# after brew update, upgrade, install, uninstall commands
function brew --wraps brew -d "brew with bundle dump"
    command brew $argv
    if contains -- update $argv || contains -- upgrade $argv || contains -- install $argv || contains -- uninstall $argv
        command brew bundle dump --file=~/.local/share/chezmoi/home/.Brewfile --no-lock --force --brews --casks --taps
    end
end

function appid -d "Get the application id from the bundle identifier"
    if test (count $argv) -eq 0
        echo "Usage: appid <bundle_id>"
        return
    end

    set -l bundle_id $argv[1]
    set -l app_id (osascript -e "id of app \"$bundle_id\"")
    echo $app_id
end

# OpenAI
set -gx OPENAI_API_KEY (pass show openai/api/token)
