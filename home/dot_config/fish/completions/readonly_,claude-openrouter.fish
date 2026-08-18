set -l _or_catalog "$__fish_config_dir/functions/__openrouter_catalog.fish"
test -f $_or_catalog; and source $_or_catalog

complete -c ',claude-openrouter' -w claude
complete -c ',claude-openrouter' -s m -l model -x -a '(__openrouter_catalog_models)' -d 'OpenRouter model id (default deepseek/deepseek-v4-flash-0731)'
complete -c ',claude-openrouter' -l effort -x -a '(__openrouter_catalog_efforts)' -d 'Reasoning effort (default max; none disables)'
complete -c ',claude-openrouter' -l reasoning-effort -x -a '(__openrouter_catalog_efforts)' -d 'Alias for --effort'
complete -c ',claude-openrouter' -l thinking -x -a '(__openrouter_catalog_efforts)' -d 'Alias for --effort'
complete -c ',claude-openrouter' -l no-thinking -d 'Minimal reasoning effort'
complete -c ',claude-openrouter' -s h -l help -d 'Show Claude Code help'
