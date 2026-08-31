# Completions for Cursor's local llama.cpp launcher.

set -l __cursor_llama_cpp_models nemotron-3.5 qwen3.5-9b qwen3.8-27b qwen3.8-27b-instruct
set -l __cursor_llama_cpp_subs install-shell-integration uninstall-shell-integration login logout mcp plugin worker status whoami models bedrock about update create-chat generate-rule rule agent ls resume help

complete -c ',cursor-llama-cpp' -f

for subcommand in $__cursor_llama_cpp_subs
    complete -c ',cursor-llama-cpp' -n "not __fish_seen_subcommand_from $__cursor_llama_cpp_subs" -a $subcommand
end

complete -c ',cursor-llama-cpp' -s v -l version -d 'Output the version number'
complete -c ',cursor-llama-cpp' -s H -l header -x -d "Add custom header (format: 'Name: Value')"
complete -c ',cursor-llama-cpp' -s p -l print -d 'Print responses to console'
complete -c ',cursor-llama-cpp' -l output-format -x -a 'text json stream-json' -d 'Output format (only with --print)'
complete -c ',cursor-llama-cpp' -l stream-partial-output -d 'Stream partial output as text deltas'
complete -c ',cursor-llama-cpp' -l mode -x -a 'plan ask' -d 'Start in the given execution mode'
complete -c ',cursor-llama-cpp' -l plan -d 'Start in plan mode'
complete -c ',cursor-llama-cpp' -l resume -x -d 'Select a session to resume'
complete -c ',cursor-llama-cpp' -l continue -d 'Continue previous session'
complete -c ',cursor-llama-cpp' -s m -l model -x -a "$__cursor_llama_cpp_models" -d 'Override local model id'
complete -c ',cursor-llama-cpp' -l list-models -d 'List available models and exit'
complete -c ',cursor-llama-cpp' -s f -l force -d 'Force allow commands unless explicitly denied'
complete -c ',cursor-llama-cpp' -l yolo -d 'Alias for --force'
complete -c ',cursor-llama-cpp' -l auto-review -d 'Use Auto-review'
complete -c ',cursor-llama-cpp' -l sandbox -x -a 'enabled disabled' -d 'Enable or disable sandbox mode'
complete -c ',cursor-llama-cpp' -l approve-mcps -d 'Automatically approve all MCP servers'
complete -c ',cursor-llama-cpp' -l trust -d 'Trust the current workspace without prompting'
complete -c ',cursor-llama-cpp' -l workspace -x -d 'Workspace directory or saved workspace name'
complete -c ',cursor-llama-cpp' -l add-dir -x -d 'Add an additional workspace root'
complete -c ',cursor-llama-cpp' -l plugin-dir -x -d 'Load a local plugin directory'
complete -c ',cursor-llama-cpp' -s w -l worktree -x -d 'Start in an isolated git worktree'
complete -c ',cursor-llama-cpp' -l worktree-base -x -d 'Branch or ref for the worktree'
complete -c ',cursor-llama-cpp' -l skip-worktree-setup -d 'Skip worktree setup scripts'
complete -c ',cursor-llama-cpp' -s h -l help -d 'Show Cursor Agent help'
