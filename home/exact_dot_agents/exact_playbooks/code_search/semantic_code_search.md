# Semantic Code Search Playbook

Use this playbook for conceptual investigations using semantic-code-search MCP tools.

When triggered:

- prioritize semantic-code-search MCP tools over mechanical grepping
- provide context (paths, snippets, precise queries) to maximize accuracy

Common trigger in reviews:

- Base-branch context for reviews (PR or local changes): learn how base works and
  what invariants exist, then compare against the local diff.

When NOT to use:

- simple string/filename lookup: use local `rg` or file listing
- as a replacement for local review of branch changes: use local repo tools for
  exact state (`git diff`, file reads, tests). SCSI is for base context.
- purely mechanical pattern matching to drive a replace/edit: use local `rg`
- current repo is not indexed (not present in `list_indices`): do not use semantic code search

Important limitation:

- the semantic index is a snapshot (typically of `main`)
- use it to learn base-branch context and patterns
- for PRs/branches, compare semantic (base) findings against local branch diff for what actually changed

Review output contract (when invoked from a review playbook):

- Record the selected index (or "none") and include a `Base context:` line in
  the review output:
  - `Base context: SCSI=<index>|none (list_indices checked; <reason>), base=<branch>, diff=<base>...HEAD`
  - reviewer metadata only; do not include in GitHub comment bodies

Review preflight (blocking):

- If the review playbook requires base-branch context and the user did not
  provide an index name, run `list_indices` BEFORE you proceed.

How to run `list_indices`:

- Prefer calling both MCP servers (when available):
  - `scsi-main_list_indices`
  - `scsi-local_list_indices`
- If one does not exist/fails but the other works, proceed with the working one.
- If both fail or neither exists, treat SCSI as unavailable.
- You are not allowed to skip SCSI just because the user didn't provide an index
  name.
- If the repo is indexed, you MUST invoke at least one SCSI tool to establish
  base-branch context.
- Only skip SCSI if:
  - `list_indices` proves the repo is not indexed, OR
  - the SCSI tools are unavailable (cannot call `list_indices`), OR
  - the user explicitly requests no semantic search.

Allowed `<reason>` values (reviews):

- `SCSI used`
- `not indexed`
- `tools unavailable`
- `user-selected none`

Hard gate (required): repo must be indexed

- semantic search is only valid for repos present in `list_indices`
- if current repo is not represented, fall back to local search (`rg`/file reads) and normal git comparisons

Index usage:

- if the user provides an index name, use it directly
- otherwise:
  - always run `list_indices` first (do not guess)
    - if you have both `scsi-main` and `scsi-local`, run `list_indices` on both before concluding "not indexed"
  - if `list_indices` returns no usable results, do not use semantic search (fall back to local sources)
  - if `list_indices` returns an obvious match for the current repo, use it
    - "obvious" means you can justify the selection from evidence (for example: index name clearly includes the repo name, or it is the only index that matches the repo you’re in)
  - if multiple indices look plausible, ask the user which index to use (default: the one that most clearly matches the current repo and base branch)

Passing `index`:

- once you have a candidate index from `list_indices`, pass it explicitly to SCSI tools instead of relying on an implicit/default index
  - exception: only omit `index` if you can prove (via evidence) that the MCP default points at the same index you selected
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
