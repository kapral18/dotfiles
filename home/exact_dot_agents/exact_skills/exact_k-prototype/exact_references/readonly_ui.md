# UI Prototype

Generate **several radically different UI variations** on a single route, switchable from a floating bottom bar.
The user flips between variants in the browser, picks one (or steals bits from each), then throws the rest away.

Right shape when: "what should this page look like", "show a few options for this dashboard before committing", "try a different layout".
If the question is about logic/state, wrong branch — use `logic.md`.

## Two sub-shapes — strongly prefer sub-shape A

A UI prototype is far easier to judge when it butts up against the rest of the app — real header, real sidebar, real data, real density.
A throwaway route on its own is a vacuum where every variant looks fine.

### Sub-shape A — adjustment to an existing page (preferred)

The route already exists. Variants render **on the same route**, gated by a `?variant=` URL search param.
Existing data fetching, params, and auth all stay — only the rendering swaps.
If the thing being prototyped has no page yet but _would naturally live inside one_ (a new section of the dashboard, a new card, a new step in a flow), that is still sub-shape A: mount the variants inside the host page.

### Sub-shape B — a new page (last resort)

Only when the thing genuinely has no existing page to live inside.
Create a **throwaway route** following the project's existing routing convention; name it so it is obviously a prototype.
Same `?variant=` pattern. Sanity-check first: is there really no existing page this could embed in?
An empty route hides design problems a populated one exposes.

The floating bottom bar is identical in both sub-shapes.

## Process

### 1. State the question and pick N

Default to **3 variants**; more than 5 stops being radically different and becomes noise — cap there.
Write the plan in one line in a top-of-file comment: "Three variants of the settings page, switchable via `?variant=`, on the existing `/settings` route."

### 2. Generate radically different variants

Hold each to the page's purpose and the data it has access to, and to the project's component/styling system (Tailwind, shadcn, MUI, plain CSS — whatever is there).
Give each a clear exported name (`VariantA`, `VariantB`, `VariantC`).
Variants must be **structurally different** — different layout, information hierarchy, primary affordance, not just different colours.
Three slightly-tweaked card grids is wallpaper, not a prototype.
If two drafts come out too similar, redo one with explicit "do not use a card grid" guidance.

### 3. Wire them together

A single switcher on the route reads `?variant=` and renders the matching variant plus the switcher.
For sub-shape A keep all existing data fetching above the switcher; only the rendered subtree changes per variant.
For sub-shape B the throwaway route mounts the same switcher.

### 4. Build the floating switcher

A small fixed bar at bottom-centre: left arrow (previous, wraps), variant label (current key plus exported name, e.g. `B — Sidebar layout`), right arrow (next, wraps).
Behaviour:

- Clicking an arrow updates the URL search param via the framework's router so the variant is shareable and reload-stable.
- `←`/`→` keys also cycle, but do not intercept them when an `<input>`, `<textarea>`, or `[contenteditable]` is focused.
- Visually distinct from the page (high-contrast pill, subtle shadow) so it is obviously not part of the design being evaluated.
- Hidden in production builds — gate on `NODE_ENV !== 'production'` so a stray merge cannot ship the bar.

Put the switcher in one shared component so both sub-shapes reuse it.

### 5. Hand it over

Surface the URL and the `?variant=` keys.
The interesting feedback is usually "I want the header from B with the sidebar from C" — that is the actual design they want.

### 6. Capture the answer and clean up

Once a variant wins, write down which and why (commit, PR, issue, `,ai-kb`, or a `NOTES.md`).
Then, for sub-shape A delete the losing variants and the switcher and fold the winner into the page;
for sub-shape B promote the winner to a real route and delete the throwaway route and switcher.
Do not leave variant components or the switcher lying around.

## Anti-patterns

- **Variants that differ only in colour or copy** — a tweak, not a prototype. Real variants disagree about structure.
- **Sharing too much between variants** — a shared `<Header>` is fine; a shared `<Layout>` defeats the point.
- **Wiring variants to real mutations** — read-only prototypes are fine; point mutations at a stub.
- **Promoting prototype code straight to production** — it was written under prototype constraints; rewrite it properly when folding in.
