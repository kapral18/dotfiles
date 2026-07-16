complete -c ,mcp-token -f
complete -c ,mcp-token -n "not __fish_seen_subcommand_from slack scsi-main" -a slack -d "Slack MCP server"
complete -c ,mcp-token -n "not __fish_seen_subcommand_from slack scsi-main" -a scsi-main -d "Semantic Code Search MCP server"
complete -c ,mcp-token -l bearer -d 'Print "Bearer <token>" for an Authorization header'
complete -c ,mcp-token -l json -d "Print {token, source, seconds_left} as JSON"
complete -c ,mcp-token -l launch-json -d "With --login, capture launch metadata and defer proactive rotation"
complete -c ,mcp-token -l login -d "Ensure a fresh token: silent refresh-grant rotation via cursor when short/stale, browser flow as last resort"
complete -c ,mcp-token -l rotate -d "Silently rotate a short token without browser fallback"
complete -c ,mcp-token -l force -d "With --login, re-authenticate even if the cached token is still valid"
complete -c ,mcp-token -l quiet -d "With --login or --rotate, suppress status and auth helper output"
complete -c ,mcp-token -s h -l help -d "Show help"
