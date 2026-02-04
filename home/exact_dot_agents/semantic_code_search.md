# Semantic Code Search Workflow

When triggered, ALWAYS prioritize the semantic-code-search MCP tools over built-in search mechanisms.

Provide context (paths, snippets, precise queries) to maximize accuracy.

Index usage:

- Never use `list_indices` — always use the index name provided by the user directly.
- If a search returns no results or the index is not found in one MCP, try the other MCP before giving up.
- Two MCP servers are available: `scsi-main` (shared/team indices) and `scsi-local` (user-specific indices).

Tool selection guidelines:

| Tool                    | Use case                     | Output                                               |
| ----------------------- | ---------------------------- | ---------------------------------------------------- |
| `map_symbols_by_query`  | Known symbol/directory names | All matching files; shows symbol density             |
| `semantic_code_search`  | Conceptual/unfamiliar code   | Top snippets with scores; answers "How does X work?" |
| `discover_directories`  | Locate relevant directories  | Top directories ranked by relevance; use first       |
| `symbol_analysis`       | Deep dive on one symbol      | Definitions, usages, types, related symbols          |
| `read_file_from_chunks` | Read complete files          | Full stitched view for examining implementations     |
