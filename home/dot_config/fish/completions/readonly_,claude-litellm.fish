complete -c ',claude-litellm' -w claude
complete -c ',claude-litellm' -s m -l model -x -a '(__comma_provider_models litellm)' -d 'Select LiteLLM gateway model'
complete -c ',claude-litellm' -s h -l help -d 'Show Claude Code help'
