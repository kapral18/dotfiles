---
name: walkthrough
description: Explore and visualize codebase architecture, flows, and component relationships through interactive diagrams. Use when asked to walk through systems, explain flows, show architectures, or understand how components interact. Do NOT use for quick one-off lookups or code edits.
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

- Simple file reading (use Read tool instead)
- Single file analysis without relationship context
- Modifying or editing code
- Quick lookups of specific symbols or functions

## Workflow

### Step 1: Explore the Codebase

Use the `walkthrough` tool to explore the codebase structure and relationships. Provide:

- `topic`: Clear question or area to explore (e.g., "How does authentication flow?", "Walk me through the database layer")
- `context`: Optional additional context about what the user wants to understand

The walkthrough tool invokes a planner subagent with access to Read, Grep, glob, and finder to build understanding by following references, imports, and call sites.

When semantic code search helps:

- If you are investigating a PR and need additional context from `main` (existing behavior, patterns, related call sites),
  use `~/.agents/skills/semantic-code-search/SKILL.md` to query the indexed snapshot, but ONLY if the current repo is
  indexed (present in `list_indices`).
- Treat semantic results as base-branch context only; validate the actual change by reading the local branch diff.

### Step 2: Generate the Diagram

Once exploration is complete, call `walkthrough_diagram` to render an interactive ASCII diagram. Provide:

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

**User asks:** "Walk me through how authentication works in this codebase"

1. Call `walkthrough` to explore auth-related code
2. Call `walkthrough_diagram` with the resulting diagram structure:

```
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

- **Progressive disclosure**: Start with high-level architecture, then explore specific components
- **Follow the code**: Use actual imports, function calls, and file structure
- **Link to evidence**: Always provide file paths and code snippets for clickable nodes
- **Clarify relationships**: Show data flow, control flow, and dependency relationships
- **Use concrete examples**: Reference actual functions, files, and configurations

## Built-in Tools

The walkthrough skill has access to:

- `walkthrough(topic, context)` — Explore codebase relationships and structure
- `walkthrough_diagram(code, summary, nodes)` — Render interactive diagram

Both tools are built into Amp and do not require external configuration.
