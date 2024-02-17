# FISH
set fish_greeting

# Lang
set -gx LC_ALL en_US.UTF-8
set -gx LANG en_US.UTF-8

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

# OpenAI
set -gx OPENAI_API_KEY (pass show openai/api/token)

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

# Paths
fish_add_path /usr/local/opt/libpq/bin
fish_add_path /usr/local/opt/ruby/bin
fish_add_path /usr/local/opt/ssh-copy-id/bin
fish_add_path /usr/local/opt/coreutils/libexec/gnubin
fish_add_path /usr/local/sbin
fish_add_path /opt/homebrew/sbin
fish_add_path /opt/homebrew/bin
fish_add_path $RBENV_ROOT/bin
fish_add_path $PYENV_ROOT/bin
fish_add_path $GOPATH/bin
fish_add_path /Users/kapral18/.cargo/bin
fish_add_path /Users/kapral18/.local/bin
fish_add_path /Users/kapral18/bin

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

## bass enforced nvm
function nvm
    bass source ~/.nvm/nvm.sh --no-use ';' nvm $argv
end
