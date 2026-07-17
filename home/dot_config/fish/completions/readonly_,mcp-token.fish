complete -c ,mcp-token -f
complete -c ,mcp-token -n "not __fish_seen_subcommand_from slack scsi-main" -a slack -d "Slack MCP server"
complete -c ,mcp-token -n "not __fish_seen_subcommand_from slack scsi-main" -a scsi-main -d "Semantic Code Search MCP server"
complete -c ,mcp-token -l bearer -d 'Print "Bearer <token>" for an Authorization header'
complete -c ,mcp-token -l json -d "Print {token, source, seconds_left} as JSON"
complete -c ,mcp-token -l login -d "Ensure a fresh token: silent refresh-grant rotation via cursor when short/stale, browser flow as last resort"
complete -c ,mcp-token -l bridge -d "Serve a stdio MCP bridge that injects a fresh bearer per request"
complete -c ,mcp-token -l url -d "With --bridge, the streamable-HTTP MCP endpoint to forward to" -r
complete -c ,mcp-token -l no-proactive-rotation -d "With --login, keep proactive rotation off the critical path; critical/expired/revoked still block"
complete -c ,mcp-token -l force -d "With --login, re-authenticate even if the cached token is still valid"
complete -c ,mcp-token -l quiet -d "With --login, suppress status and auth helper output"
complete -c ,mcp-token -s h -l help -d "Show help"
