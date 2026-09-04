# Diagram nodes

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
             +-----------------+
             |  Auth Service   |
             +--------+--------+
                      |
        +-------------+-------------+
        |             |             |
 +------+-------+ +---+--------+ +--+-------------+
 | Login        | | Token      | | Verify         |
 | Endpoint     | | Generation | | Middleware     |
 +------+-------+ +---+--------+ +--+-------------+
        |             |             |
  +-----+-----+ +-----+-----+ +-----+-----+
  | Token     | | Validate  | | Validate  |
  | Storage   | | Token     | | Token     |
  +-----------+ +-----------+ +-----------+
```

Then provide node metadata for each component with descriptions and links.
