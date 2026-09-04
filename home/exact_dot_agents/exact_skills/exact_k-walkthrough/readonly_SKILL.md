---
name: k-walkthrough
description: "Explore a codebase interactively: trace execution flows, map component relationships, and render architectural diagrams."
disable-model-invocation: true
---

# Walkthrough Skill

Create interactive exploratory diagrams for understanding codebase architecture and system design.

## When to Use

- Exploring codebase architecture and structure
- Understanding code flows and execution paths
- Visualizing relationships between components, modules, or services
- Onboarding to unfamiliar codebases
- Documenting complex system interactions
- Showing "how X works" or "how components connect"

## When NOT to Use

- Semantic code search alone (use `k-semantic-code-search` directly when the user explicitly asks for SCSI-style investigation, not a walkthrough)
- Simple file reading
- Single file analysis without relationship context
- Modifying or editing code
- Quick lookups of specific symbols or functions

## First Actions

1. Restate the system/question you are explaining and the boundary of the walkthrough.
2. Identify likely entrypoints, main components, and evidence sources.
3. Decide whether the user's goal needs a diagram or a written walkthrough.

## Workflow

### Step 1: Explore the Codebase

Explore codebase structure and relationships by following references, imports, and call sites.

If your environment provides dedicated walkthrough tooling (for example a `walkthrough(...)` explorer and a `walkthrough_diagram(...)` renderer), prefer that over manual exploration.
If those tools are not available, do the same workflow using local file reads and searches.

When using a walkthrough tool, provide:

- `topic`: the specific question/area to explore (example: "How does auth flow work?")
- `context`: optional extra constraints or what the user cares about

When semantic code search helps:

- If you are investigating a PR and need additional context from `main` (existing behavior, patterns, related call sites), use `~/.agents/skills/k-semantic-code-search/SKILL.md` to query the indexed snapshot, but ONLY if the current repo is indexed (present in `list_indices`).
  Run `list_indices` first; do not guess an index.
- Treat semantic results as base-branch context only; validate the actual change by reading the local branch diff.

### Step 2: Present The Walkthrough

Present the walkthrough once every node/step in the stated boundary is backed by a concrete evidence anchor (file path + symbol or call site), or the user has narrowed the boundary.

- If the system is complex or the user asked for a diagram, render an interactive ASCII diagram.
- If a diagram would add little value, give a concise written walkthrough with the same evidence trail instead.

When rendering a diagram, provide:

- `code`: ASCII diagram showing component relationships
- `summary`: One-sentence description of what the diagram illustrates
- `nodes`: Metadata for clickable nodes with titles, descriptions, and links

## Output

- Give an evidence-backed walkthrough with file/path references.
- If you used semantic code search, say it was supporting base context rather than the sole source of truth.
- Render a diagram only when it materially improves understanding.

## Node Metadata and diagram example

Before rendering a diagram, read and follow `~/.agents/skills/k-walkthrough/references/diagram-nodes.md` in full for node metadata and the complete example.
Written walkthroughs do not require this reference.

## Tips for Effective Walkthroughs

- Progressive disclosure: start high-level, then explore specific components
- Clarify relationships: show data flow, control flow, and dependency relationships

## Tools (If Available)

Some agent environments expose walkthrough-specific tools. If present, they are typically used like:

- `walkthrough(topic, context)` to explore relationships and structure
- `walkthrough_diagram(code, summary, nodes)` to render an interactive diagram
