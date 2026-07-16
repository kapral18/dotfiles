---
name: k-code-quality-react
description: "Use when editing, reviewing, or refactoring React/JSX/TSX components, hooks, or client-side UI behavior."
---

# React Code Quality

Use this for React-specific implementation guidance.
The `~/.agents/skills/k-code-quality/SKILL.md` skill still applies unless local project rules are stricter.

## Component Structure

- Use one functional React component per file when writing React.
- Prefer hooks and composition over class components or inheritance.
- Keep component props explicit and typed.
- Split a component only when it reduces real complexity or matches an existing local pattern.
- Do not add configurability, callbacks, context, memoization, or state just because it might be useful later.

## Hooks And State

- Keep hooks unconditional and ordered.
- Prefer derived values over duplicated state.
- Use effects for synchronization with external systems, not for derivable render state.
- Keep effect dependencies honest; do not silence dependency rules without a verified local reason.
- Treat loading, empty, error, and disabled states as user-visible behavior that needs verification when touched.

## Secondary Skill Escalation

Do not load secondary skills until read/diff evidence proves the surface is in scope.

- If markup, styling, or accessibility semantics change, also load the `~/.agents/skills/k-code-quality-web/SKILL.md` skill.

## UI Behavior

- Preserve keyboard and focus behavior when changing interactive components.
- Verify user-visible behavior with the smallest practical rendered check when the change affects interaction or layout.
