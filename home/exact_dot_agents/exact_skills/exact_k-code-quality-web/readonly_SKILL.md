---
name: k-code-quality-web
description: "Use for browser-rendered markup, CSS, layout, visual states, accessibility, or focus behavior edits/reviews."
---

# Web Markup And Styling Quality

Use this for browser-rendered markup and styling.

## Secondary Skill Escalation

Do not load secondary skills until read/diff evidence proves the surface is in scope.

- If the concrete web surface is React/JSX/TSX, also load the `~/.agents/skills/k-code-quality-react/SKILL.md` skill.

## Markup And Semantics

- Prefer semantic HTML and existing design-system primitives over custom markup.
- Preserve accessible names, roles, focus order, and keyboard reachability.
- Keep semantic elements in place; replace one with a generic container only when the local component API requires it.
- Keep ARIA minimal and accurate; fix incorrect structure directly rather than papering over it with ARIA.

## CSS And Layout

- Match the local styling system: CSS modules, utility classes, design tokens, variables, or component props.
- Prefer existing spacing, color, typography, and breakpoint tokens over new magic values.
- Keep responsive, overflow, empty, loading, disabled, hover, focus, and error states in mind when styling changes.
- Scope selectors to the intended component or page; a broad selector can leak outside it.

## Verification

- For user-visible UI changes, verify the rendered state with the smallest practical browser or screenshot check.
- When visual verification is not possible, state the gap and the static evidence checked instead.
