# Walkthrough Playbook

Create interactive exploratory diagrams for understanding codebase architecture and system design.

## When to Use

- Exploring codebase architecture and structure
- Understanding code flows and execution paths
- Visualizing relationships between components, modules, or services
- Onboarding to unfamiliar codebases
- Documenting complex system interactions
- Showing "how X works" or "how components connect"

## When NOT to Use

- Simple file reading
- Single file analysis without relationship context
- Modifying or editing code
- Quick lookups of specific symbols or functions

## Workflow

### Step 1: Explore the Codebase

Explore codebase structure and relationships by following references, imports, and call sites.

If your environment provides dedicated walkthrough tooling (for example a
`walkthrough(...)` explorer and a `walkthrough_diagram(...)` renderer), prefer
that over manual exploration. If those tools are not available, do the same
workflow using local file reads and searches.

When using a walkthrough tool, provide:

- `topic`: the specific question/area to explore (example: "How does auth flow work?")
- `context`: optional extra constraints or what the user cares about

When semantic code search helps:

- If you are investigating a PR and need additional context from `main` (existing behavior, patterns, related call sites),
  use `~/.agents/playbooks/code_search/semantic_code_search.md` to query the indexed snapshot, but ONLY if the current repo is
  indexed (present in `list_indices`).
- Treat semantic results as base-branch context only; validate the actual change by reading the local branch diff.

### Step 2: Generate the Diagram

Once exploration is complete, render an interactive ASCII diagram.

Provide:

- `code`: ASCII diagram showing component relationships
- `summary`: One-sentence description of what the diagram illustrates
- `nodes`: Metadata for clickable nodes with titles, descriptions, and links

## Node Metadata

Each node in the diagram can include:

- `title`: Display name shown in the details panel
- `description`: Detailed explanation of the component (supports Markdown)
- `links`: Array of `{label, url}` for related files or documentation
- `codeSnippet`: Optional code snippet to display
- `threadID`: Optional thread ID linking to a subthread that explores the node in detail

## Example Usage

User asks: "Walk me through how authentication works in this codebase"

1. Explore auth-related code
2. Render a diagram with the resulting structure:

```text
                ┌─────────────────┐
                │  Auth Service   │
                └────────┬────────┘
                         │
           ┌─────────────┼──────────────┐
           │             │              │
    ┌──────▼────┐  ┌────▼────┐  ┌─────▼──────┐
    │   Login   │  │  Token  │  │   Verify   │
    │ Endpoint  │  │Generation│  │ Middleware │
    └──────┬────┘  └────┬────┘  └─────┬──────┘
           │            │             │
      ┌────▼────┐  ┌────▼────┐  ┌────▼──────┐
      │  Token  │  │ Validate│  │  Validate │
      │ Storage │  │  Token  │  │   Token   │
      └─────────┘  └─────────┘  └───────────┘
```

Then provide node metadata for each component with descriptions and links.

## Tips for Effective Walkthroughs

- Progressive disclosure: start high-level, then explore specific components
- Follow the code: use actual imports, function calls, and file structure
- Link to evidence: provide file paths and small snippets for nodes
- Clarify relationships: show data flow, control flow, and dependency relationships
- Use concrete examples: reference actual functions, files, and configurations

## Tools (If Available)

Some agent environments expose walkthrough-specific tools. If present, they are
typically used like:

- `walkthrough(topic, context)` to explore relationships and structure
- `walkthrough_diagram(code, summary, nodes)` to render an interactive diagram
