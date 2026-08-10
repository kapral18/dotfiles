complete -c ',codex-openrouter' -f
complete -c ',codex-openrouter' -s m -l model -x -d 'OpenRouter model id (default deepseek/deepseek-v4-flash-0731)'
complete -c ',codex-openrouter' -l effort -x -a 'none minimal low medium high xhigh max' -d 'Reasoning effort (default max; none disables)'
complete -c ',codex-openrouter' -l reasoning-effort -x -a 'none minimal low medium high xhigh max' -d 'Alias for --effort'
complete -c ',codex-openrouter' -l thinking -x -a 'none minimal low medium high xhigh max' -d 'Alias for --effort'
complete -c ',codex-openrouter' -l no-thinking -d 'Minimal reasoning effort'
complete -c ',codex-openrouter' -l help -s h -d 'Show Codex help'
