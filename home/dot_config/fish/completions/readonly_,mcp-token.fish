complete -c ,mcp-token -f
complete -c ,mcp-token -n "not __fish_seen_subcommand_from slack scsi-main" -a slack -d "Slack MCP server"
complete -c ,mcp-token -n "not __fish_seen_subcommand_from slack scsi-main" -a scsi-main -d "Semantic Code Search MCP server"
complete -c ,mcp-token -l bearer -d 'Print "Bearer <token>" for an Authorization header'
complete -c ,mcp-token -l json -d "Print {token, source, seconds_left} as JSON"
complete -c ,mcp-token -l login -d "Refresh the token via cursor's OAuth flow if stale (cursor-agent mcp login)"
complete -c ,mcp-token -l force -d "With --login, re-authenticate even if the cached token is still valid"
complete -c ,mcp-token -l quiet -d "With --login, suppress status and auth helper output"
complete -c ,mcp-token -s h -l help -d "Show help"
