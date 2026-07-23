complete -c ',claude-vertex' -w claude
complete -c ',claude-vertex' -s m -l model -x -a '(__comma_provider_models vertex)' -d 'Select curated Vertex model'
complete -c ',claude-vertex' -l effort -x -a 'minimal low medium high xhigh max' -d 'Set provider reasoning effort'
complete -c ',claude-vertex' -l reasoning-effort -x -a 'minimal low medium high xhigh max' -d 'Set provider reasoning effort'
complete -c ',claude-vertex' -l thinking -a 'minimal low medium high xhigh max' -d 'Enable provider thinking'
complete -c ',claude-vertex' -l no-thinking -d 'Disable thinking for supported Claude models'
complete -c ',claude-vertex' -s h -l help -d 'Show Vertex wrapper help'
