set -l _or_catalog "$__fish_config_dir/functions/__openrouter_catalog.fish"
test -f $_or_catalog; and source $_or_catalog

complete -c ',cursor-openrouter' -f
complete -c ',cursor-openrouter' -s m -l model -x -a '(__openrouter_catalog_models)' -d 'OpenRouter model id (default deepseek/deepseek-v4-flash-0731)'
complete -c ',cursor-openrouter' -l effort -x -a '(__openrouter_catalog_efforts)' -d 'Reasoning effort (default max; none disables)'
complete -c ',cursor-openrouter' -l reasoning-effort -x -a '(__openrouter_catalog_efforts)' -d 'Alias for --effort'
complete -c ',cursor-openrouter' -l thinking -x -a '(__openrouter_catalog_efforts)' -d 'Alias for --effort'
complete -c ',cursor-openrouter' -l no-thinking -d 'Minimal reasoning effort'
complete -c ',cursor-openrouter' -l no-shim -d 'Direct OpenRouter route: skip the model guardrail and strict fix (only for preset-less models)'
complete -c ',cursor-openrouter' -l print -s p -d 'Print responses to console (non-interactive)'
complete -c ',cursor-openrouter' -l output-format -x -a 'text json stream-json' -d 'Output format (only with --print)'
complete -c ',cursor-openrouter' -l stream-partial-output -d 'Stream partial output as text deltas'
complete -c ',cursor-openrouter' -l mode -x -a 'plan ask' -d 'Start in the given execution mode'
complete -c ',cursor-openrouter' -l plan -d 'Start in plan mode'
complete -c ',cursor-openrouter' -l resume -x -d 'Select a session to resume'
complete -c ',cursor-openrouter' -l continue -d 'Continue previous session'
complete -c ',cursor-openrouter' -l force -s f -d 'Force allow commands unless explicitly denied'
complete -c ',cursor-openrouter' -l yolo -d 'Alias for --force'
complete -c ',cursor-openrouter' -l trust -d 'Trust the current workspace without prompting'
complete -c ',cursor-openrouter' -l help -s h -d 'Show Cursor Agent help'
