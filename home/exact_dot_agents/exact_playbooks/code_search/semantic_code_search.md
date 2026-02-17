# Semantic Code Search Playbook

Use this playbook for conceptual investigations using semantic-code-search MCP tools.

When triggered:

- prioritize semantic-code-search MCP tools over mechanical grepping
- provide context (paths, snippets, precise queries) to maximize accuracy

When NOT to use:

- simple string/filename lookup: use local `rg` or file listing
- reviewing uncommitted work or a feature branch and you need exact local state: use local repo tools
- purely mechanical pattern matching to drive a replace/edit: use local `rg`
- current repo is not indexed (not present in `list_indices`): do not use semantic code search

Important limitation:

- the semantic index is a snapshot (typically of `main`)
- use it to learn base-branch context and patterns
- for PRs/branches, compare semantic (base) findings against local branch diff for what actually changed

Hard gate (required): repo must be indexed

- semantic search is only valid for repos present in `list_indices`
- if current repo is not represented, fall back to local search (`rg`/file reads) and normal git comparisons

Index usage:

- if the user provides an index name, use it directly
- otherwise:
  - run `list_indices` and confirm current repo is represented
  - if multiple indices apply, pick the one matching the current repo's `main`
  - only then omit `index` to rely on MCP default; do not assume the default points at the correct repo
- if a search returns no results or index not found in one MCP, try the other MCP before giving up
- two MCP servers may exist: `scsi-main` (shared/team indices) and `scsi-local` (user-specific)

Tool selection guidelines:

| Tool                    | Use case                     | Output                                               |
| ----------------------- | ---------------------------- | ---------------------------------------------------- |
| `map_symbols_by_query`  | Known symbol/directory names | All matching files; shows symbol density             |
| `semantic_code_search`  | Conceptual/unfamiliar code   | Top snippets with scores; answers "How does X work?" |
| `discover_directories`  | Locate relevant directories  | Top directories ranked by relevance; use first       |
| `symbol_analysis`       | Deep dive on one symbol      | Definitions, usages, types, related symbols          |
| `read_file_from_chunks` | Read complete files          | Full stitched view for examining implementations     |
