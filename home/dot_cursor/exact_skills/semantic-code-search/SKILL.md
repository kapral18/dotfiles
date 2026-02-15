---
name: semantic-code-search
description: "Semantic code search using the semantic-code-search MCP tools (scsi-main/scsi-local): semantic queries, directory discovery, symbol analysis, and reading stitched files from an index. Use primarily for investigations/research on main of indexed repos; hard gate: confirm the current repo is indexed via list_indices before relying on results. It can replace advanced grepping when the goal is conceptual understanding (not mechanical pattern matching). Do NOT use for uncommitted/local-only changes, non-indexed repos, or purely mechanical find/replace."
---

# Semantic Code Search Workflow

When triggered, prioritize the semantic-code-search MCP tools over built-in
search mechanisms.

Provide context (paths, snippets, precise queries) to maximize accuracy.

When NOT to use:

- You only need a simple string/filename lookup: use `Grep`/`Glob`.
- You are reviewing uncommitted work or a feature branch and need the exact local state: use local repo tools.
- You are doing purely mechanical pattern matching to drive a replace/edit: use `Grep`/`Glob`.
- The current repo is not indexed (not present in `list_indices`): do not use semantic-code-search at all.

Important limitation:

- The semantic index is a snapshot (typically of `main`). Use it to learn base-branch context and patterns.
  For PRs/branches, compare semantic (base) findings against your local branch diff for what actually changed.

Hard gate (required): repo must be indexed

- Semantic code search is only valid for repos that exist in `list_indices`.
- If the current repo is not represented by any available index, do not proceed with semantic code search.
  Fall back to local `Grep`/`Glob`/`Read` (and normal git comparisons).

Index usage:

- If the user provides an index name, use it directly.
- If the user does NOT provide an index name:
  - Prefer `list_indices` and confirm the current repo is represented.
  - If multiple indices could apply, pick the one that clearly matches the current repo's `main` branch.
  - Only after that, you may omit `index` to rely on the MCP server's default, but do not assume the
    default points at the correct repo.
- If a search returns no results or the index is not found in one MCP, try the
  other MCP before giving up.
- Two MCP servers are available: `scsi-main` (shared/team indices) and
  `scsi-local` (user-specific indices).

Tool selection guidelines:

| Tool                    | Use case                     | Output                                               |
| ----------------------- | ---------------------------- | ---------------------------------------------------- |
| `map_symbols_by_query`  | Known symbol/directory names | All matching files; shows symbol density             |
| `semantic_code_search`  | Conceptual/unfamiliar code   | Top snippets with scores; answers "How does X work?" |
| `discover_directories`  | Locate relevant directories  | Top directories ranked by relevance; use first       |
| `symbol_analysis`       | Deep dive on one symbol      | Definitions, usages, types, related symbols          |
| `read_file_from_chunks` | Read complete files          | Full stitched view for examining implementations     |
