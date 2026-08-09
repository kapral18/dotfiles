complete -c ',claude-openrouter' -w claude
complete -c ',claude-openrouter' -s m -l model -x -d 'OpenRouter model id (default deepseek/deepseek-v4-flash-0731)'
complete -c ',claude-openrouter' -l effort -x -a 'minimal low medium high xhigh max' -d 'Reasoning effort (default max)'
complete -c ',claude-openrouter' -l reasoning-effort -x -a 'minimal low medium high xhigh max' -d 'Alias for --effort'
complete -c ',claude-openrouter' -l thinking -x -a 'minimal low medium high xhigh max' -d 'Alias for --effort'
complete -c ',claude-openrouter' -l no-thinking -d 'Minimal reasoning effort'
complete -c ',claude-openrouter' -s h -l help -d 'Show Claude Code help'
