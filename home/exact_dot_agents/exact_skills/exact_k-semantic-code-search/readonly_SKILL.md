---
name: k-semantic-code-search
description: "Use for nontrivial code-impact assessment, conceptual code search, SCSI index selection, or review base context."
---

# Semantic Code Search Skill

Use this skill for conceptual investigations using semantic-code-search MCP tools.

When triggered:

- prioritize semantic-code-search MCP tools over mechanical grepping
- provide context (paths, snippets, precise queries) to maximize accuracy
- treat explicit index-selection language as a trigger, even when the user does not name SCSI tools directly (example:
  "use `<index>` index")

Common trigger for nontrivial impact assessment:

- Base-branch context for nontrivial diagnosis, implementation, or reviews: learn how base works, which callers/consumers are affected, and what invariants exist, then compare that context against exact local state.

Do not use:

- simple string/filename lookup: use local `rg` or file listing
- as a replacement for local diagnosis, implementation, or review of branch changes:
  use local repo tools for exact state (`git diff`, file reads, tests). SCSI is for base context and impact exploration.
- purely mechanical pattern matching to drive a replace/edit: use local `rg`
- current repo is not indexed (not present in `list_indices`): do not use semantic code search

A delegated leaf that loads this skill runs the queries itself and never spawns a child.

First actions:

1. Run `list_indices` before any semantic query.
2. Verify whether the current repo is indexed and pick the single justified index, or record why none can be used.
3. Choose queries that resolve the assigned uncertainty; for nontrivial diagnosis or implementation impact, explore relevant symbols, callers, consumers, and invariants.
4. Drill down using symbol analysis and chunk reads on relevant matching paths to map full impact, then compare the result with exact local state.

Reuse valid index-selection and query evidence; do not repeat unchanged queries solely to double-check a completed assessment.
If the repo is unindexed, tools are unavailable, or the user opts out, establish impact from local sources and record the reason.

Important limitation: the semantic index is a snapshot (typically of `main`);
use it for base-branch context and patterns, then compare diagnosis/implementation/review findings against exact local state.

Review output contract (when invoked from a review skill):

- Record the selected index (or "none") and include a `Base context:` line in the review output:
  - `Base context: SCSI=<index>|none (discovery=<checked|unavailable|skipped by request>; <reason>), base=<branch>, diff=<base>...HEAD`
  - reviewer metadata only; do not include in GitHub comment bodies
  - Report `checked` only when `list_indices` returned usable discovery evidence;
    unavailable tools use `unavailable`, and an explicit opt-out uses `skipped by request`. NEVER claim a discovery check that did not run.

Review preflight (blocking):

- If the review skill requires base-branch context, run `list_indices` BEFORE you proceed (even if the user provided an index name).

How to run `list_indices`:

- Prefer calling both MCP servers (when available):
  - `scsi-main_list_indices`
  - `scsi-local_list_indices`
- If one does not exist/fails but the other works, proceed with the working one.
- If both fail or neither exists, treat SCSI as unavailable.
- `list_indices` output can exceed the harness output limit and get saved to a temp file;
  search that file for the candidate repo slug instead of re-running the call.
- When this skill applies, you must run SCSI even when the user did not provide an index name.
- When this skill applies and the repo is indexed, you MUST invoke at least one SCSI tool to establish base-branch context and relevant impact.
- Only skip SCSI if:
  - `list_indices` proves the repo is not indexed, OR
  - the SCSI tools are unavailable (cannot call `list_indices`), OR
  - the user explicitly requests no semantic search.

Allowed `<reason>` values (reviews):

- `SCSI used`
- `not indexed`
- `tools unavailable`
- `user-selected none`

Index usage:

- if the user provides an index name:
  - verify it exists in `list_indices`
  - if it does not exist, stop and ask which index to use
- otherwise:
  - if both `scsi-main` and `scsi-local` exist, run `list_indices` on both before concluding "not indexed"
  - if `list_indices` returns no usable results, fall back to local sources instead of semantic search
  - if `list_indices` returns an obvious match for the current repo, use it - "obvious" means you can justify the selection from evidence (for example: index name clearly includes the repo name, or it is the only index that matches the repo you're in)
  - if multiple equally plausible indices remain after evidence-based filtering, ask the user which index to use

Output:

- State the selected index (or `none`) and why.
- Keep semantic findings tied to concrete paths/symbols/snippets.

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

## Root moves

Only the active root/main session follows this section; a delegated leaf skips it and returns findings to its parent.
Use the strong research category for substantial context-heavy investigations;
never route symbol selection or synthesis to a cheap mechanical model. Targeted queries may remain inline.
Dispatch the whole bounded question, not each query/result.
Workers return conclusions, evidence pointers, uncertainty, and affected interfaces without a private review/verification workflow.
