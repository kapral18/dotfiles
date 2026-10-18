# Visual UI

## Direction

Read the current UI, design tokens, brand brief, and any `DESIGN.md` as evidence of intended appearance.
For a new composition, identify its audience, main action, and visual direction before choosing components.
Use existing direction when available; otherwise state a small, reversible assumption and proceed within the requested scope.
Missing `DESIGN.md` alone is not a blocker and does not require creating one.
Do not copy another product's identity unless the user requests that reference.

Choose three independent qualities from that direction: energy (quiet to bold), rhythm (regular to varied), and motion (static to choreographed).
These describe intent, not mandatory numeric settings. A calm tool can be well designed; a bold page can be coherent.
Retain a clear focal point, useful hierarchy, deliberate whitespace, and a consistent motif when the brief calls for one.
Do not make a page sterile by removing every expressive choice.
Explain a major new choice through its effect on the user, not a written justification for every decoration.

## Composition follows the content

- Build the page around what the reader needs to decide or do.
  A centered hero, three feature cards, bento grid, three pricing columns, “three steps,” or four-column footer needs content that benefits from that structure.
- Give sections and cards the space, emphasis, and composition their content needs.
  Repeated components can stay regular; do not force asymmetry or alternate layouts merely to look distinctive.
- Pricing tiers, “most popular” labels, partner logos, testimonials, counters, and certifications need real backing.
  Remove unsupported social proof. Mark illustrative data visibly, rather than making an empty product look busy.
- A screenshot, terminal, illustration, or animation should explain this product or express the requested identity.
  Show the actual CLI for a CLI product; do not substitute a fake terminal for an unrelated interface.
- Distinguish a demo, prototype, and available product.
  Show what the reader can actually use, the real installation or next step, and material limitations.
  Never imply that a mock screenshot or unavailable feature is working software.
- Keep navigation and footers to existing, relevant destinations.
  Product FAQs answer real questions or are omitted; a template is not evidence a section is needed.

## Decoration carries meaning

- Derive colors and typography from the project, readability, and intended character.
  Default gradients, a fashionable font, wide-tracked capitals, or monospace headings need the same reason as any other choice.
  Existing tokens and familiar fonts are valid.
- Use accent colors to establish priority or state. Avoid a rainbow of unrelated accents and repeated equal emphasis.
  Do not impose an arbitrary maximum palette size when data categories or a design system require more.
- Use glass, glow, shadows, background grids, textures, radius, and pill shapes where they communicate depth, grouping, state, or the requested visual language.
  Repeating an effect everywhere destroys its hierarchy; reduce competing emphasis instead of enforcing fixed dose limits.
- Keep icons consistent and useful. Do not replace a working icon library just because it is common.
  Remove arbitrary emoji, arrows, left-edge stripes, and decorative status dots that imply no action, category, or state.
- Badges should add a real fact.
  An eyebrow that repeats the heading adds reading without information; a glowing “live” dot falsely suggests a live state.
  Keep real status indicators distinguishable without unnecessary looping motion.
- Preserve the intended light or dark appearance. Do not add a theme toggle just to satisfy a checklist.
  For every supported theme, keep hierarchy, contrast, focus, and all reachable states coherent.
- Motion should explain an action, transition, or deliberate expressive moment.
  Avoid stacked entrance effects and distracting perpetual loops.
  Respect reduced-motion preferences; essential progress feedback must remain understandable without animation.

## Apps and dashboards

- Choose hierarchy from the screen's job, rather than automatically adding a sidebar, four stat cards, chart, and table.
  Put the field or event that drives the user's next decision first.
- Use real metrics and activity; name a delta's comparison period and source.
  A chart answers a specific question and has readable units and labels. Prefer a sentence when it communicates the answer better.
- Pick table columns from the actual entities and decisions. Row menus contain available actions.
  Leave missing data empty or explain it; never populate a customer field with a plausible invented person.
- Distinguish first use, an empty filter result, missing permission, loading, and failure when those states are reachable.
  Explain what happened and the next useful action, rather than supplying a generic illustration or spinner alone.
- Trace navigation, buttons, menus, and forms to real behavior.
  If an action is unavailable, remove it or expose an honest unavailable state;
  a TODO in source alone does not make a dead control acceptable.

For colors, controls, and states, read `~/.agents/skills/k-anti-slop/references/accessibility.md`.
For layout changes, read `~/.agents/skills/k-anti-slop/references/responsive.md`.
For charts, quantitative tables, or metrics in scope, read `~/.agents/skills/k-anti-slop/references/data_visualization.md`.
For product labels or state messages in scope, read `~/.agents/skills/k-anti-slop/references/interface_copy.md`.
For supported multilingual or bidirectional content affected by the change, read `~/.agents/skills/k-anti-slop/references/localization.md`.
Reuse references already loaded for this invocation.
Verify through the existing SOP; source inspection cannot establish that every rendered state was exercised.
