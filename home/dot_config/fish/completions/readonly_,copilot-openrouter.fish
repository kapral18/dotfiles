set -l _or_catalog "$__fish_config_dir/functions/__openrouter_catalog.fish"
test -f $_or_catalog; and source $_or_catalog

complete -c ',copilot-openrouter' -f
complete -c ',copilot-openrouter' -s m -l model -x -a '(__openrouter_catalog_models)' -d 'OpenRouter model id (default deepseek/deepseek-v4-flash-0731)'
complete -c ',copilot-openrouter' -l effort -x -a '(__openrouter_catalog_efforts)' -d 'Reasoning effort (default max; none disables)'
complete -c ',copilot-openrouter' -l reasoning-effort -x -a '(__openrouter_catalog_efforts)' -d 'Alias for --effort'
complete -c ',copilot-openrouter' -l thinking -x -a '(__openrouter_catalog_efforts)' -d 'Alias for --effort'
complete -c ',copilot-openrouter' -l no-thinking -d 'Minimal reasoning effort'
complete -c ',copilot-openrouter' -l prompt -s p -r -d 'Execute a prompt in non-interactive mode'
complete -c ',copilot-openrouter' -l interactive -s i -r -d 'Start interactive mode and execute prompt'
complete -c ',copilot-openrouter' -l agent -x -d 'Use a custom Copilot agent'
complete -c ',copilot-openrouter' -l allow-all -d 'Enable all permissions'
complete -c ',copilot-openrouter' -l yolo -d 'Enable all permissions'
complete -c ',copilot-openrouter' -l context -x -a 'default long_context' -d 'Set context tier'
complete -c ',copilot-openrouter' -l help -s h -d 'Show Copilot help'
