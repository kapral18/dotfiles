set -l _or_catalog "$__fish_config_dir/functions/__openrouter_catalog.fish"
test -f $_or_catalog; and source $_or_catalog

complete -c ',codex-openrouter' -f
complete -c ',codex-openrouter' -s m -l model -x -a '(__openrouter_catalog_models)' -d 'OpenRouter model id (default deepseek/deepseek-v4-flash-0731)'
complete -c ',codex-openrouter' -l effort -x -a '(__openrouter_catalog_efforts)' -d 'Reasoning effort (default max; none disables)'
complete -c ',codex-openrouter' -l reasoning-effort -x -a '(__openrouter_catalog_efforts)' -d 'Alias for --effort'
complete -c ',codex-openrouter' -l thinking -x -a '(__openrouter_catalog_efforts)' -d 'Alias for --effort'
complete -c ',codex-openrouter' -l no-thinking -d 'Minimal reasoning effort'
complete -c ',codex-openrouter' -l help -s h -d 'Show Codex help'
