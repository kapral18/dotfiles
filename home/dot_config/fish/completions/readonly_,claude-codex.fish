# Delegated lanes use wrapper-owned managed profiles; caller --agents is rejected.
complete -c ',claude-codex' -w claude
complete -c ',claude-codex' -s m -l model -x -a '(__comma_provider_models codex)' -d 'Select root Codex backend model'
complete -c ',claude-codex' -l effort -x -a 'none minimal low medium high xhigh max ultra' -d 'Set root effort; managed Claude lanes keep theirs'
complete -c ',claude-codex' -l reasoning-effort -x -a 'none minimal low medium high xhigh max ultra' -d 'Set root effort; managed Claude lanes keep theirs'
complete -c ',claude-codex' -s h -l help -d 'Show Codex subscription wrapper help'
