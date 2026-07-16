---
name: k-code-quality-web
description: "Use when editing, reviewing, or refactoring browser-rendered markup, styling, or presentation (HTML, CSS, layout, visual states, accessibility, keyboard/focus)."
---

# Web Markup And Styling Quality

Use this for browser-rendered markup and styling.

## Secondary Skill Escalation

Do not load secondary skills until read/diff evidence proves the surface is in scope.

- If the concrete web surface is React/JSX/TSX, also load the `~/.agents/skills/k-code-quality-react/SKILL.md` skill.

## Markup And Semantics

- Prefer semantic HTML and existing design-system primitives over custom markup.
- Preserve accessible names, roles, focus order, and keyboard reachability.
- Do not replace semantic elements with generic containers unless the local component API requires it.
- Keep ARIA minimal and accurate; do not use ARIA to paper over incorrect structure.

## CSS And Layout

- Match the local styling system: CSS modules, utility classes, design tokens, variables, or component props.
- Prefer existing spacing, color, typography, and breakpoint tokens over new magic values.
- Keep responsive, overflow, empty, loading, disabled, hover, focus, and error states in mind when styling changes.
- Avoid broad selectors that can leak outside the intended component or page.

## Verification

- For user-visible UI changes, verify the rendered state with the smallest practical browser or screenshot check.
- When visual verification is not possible, state the gap and the static evidence checked instead.
