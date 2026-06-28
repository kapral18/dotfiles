# Authoring rules — PR presentation

These are the design laws the template encodes.
The presentation exists to let a reviewer **get the accurate, detailed picture before opening the diff**, at lower cognitive cost.
It is a **review-readiness map**, not a review: the reader should finish it knowing the system, the load-bearing lines, and
the order to inspect GitHub.
Concepts introduced by the PR are first-class content, not incidental prose.
If a choice doesn't serve that, cut it.

## The preflight: make the context visible before HTML

Do not start filling the template until you have a compact authoring preflight.
It is the working map that keeps the page from becoming "the diff, but prettier":

- **Thesis:** one sentence naming the reviewer-visible outcome.
- **Audience:** the reviewer level and system context you are writing for.
- **Evidence cache:** whether prior `/tmp/specs` or `/tmp/present-pr` evidence is being reused, the PR/head SHA it matches, and
  which sources were refreshed.
- **Review-readiness map:** mental model, layered explanation, change topology, load-bearing line index, invariants/non-changes,
  risk-attention map, and GitHub handoff order.
- **Introduced concepts inventory:** each business/domain concept or logic layer the PR adds or changes, its source anchors,
  what/how/why explanation, left-sidebar label, right-sidebar note, and the medium that teaches it fastest.
- **Classification ledger:** every changed file/hunk exactly once, with role (`PRIMARY`, `SUPPORTING`, `GUARDRAIL`, `CLEANUP`),
  source anchor, and one-line purpose.
- **Act II chain:** 1-3 beats in causal order.
  Each beat has a bridge from the previous beat, one primary medium, and the exact diff line or image it needs.
- **Compression plan:** which files stay in the Act IV ledger only, which invariants become cards,
  which scorecard claims close the story, and which command outputs must stay summarized.
- **Image budget:** default one Act I contrast image; add a second only when it carries a distinct flow/state idea.
  Use deterministic HTML/diff beats for exact labels, symbol lists, and code-line insights.
- **Verification checklist:** no unfilled placeholder tokens, every referenced `nb-*` image exists,
  concept/sidebar references are consistent, every changed file/group appears in the ledger, code is HTML-escaped, and
  no idea is repeated in multiple adjacent media.

## Review-readiness map: understand before judging

The page should make the reviewer ready to review; it should not review for them.

- **Mental model:** one compact before/after and why-now block. This answers "what system did I just enter?"
- **Layered explanation:** business concept -> domain/data shape -> API/contract -> state/flow -> UI/runtime -> tests/guardrails.
  Omit layers that truly do not exist, but never hide a layer that carries behavior.
- **Change topology:** group files by responsibility and dependency, not by path order.
  Name the group, its role, the files, and which group it enables or constrains.
- **Load-bearing line index:** list the exact hunks/lines a reviewer should recognize before GitHub.
  Each row says source anchor, mechanism, why it matters, and where it appears in the page.
- **Invariants/non-changes:** explicitly say what stayed true. This prevents reviewers from spending attention on preserved behavior.
- **Risk-attention map:** name areas to inspect later without claiming a defect.
  Use phrasing like "check boundary conditions around X" or "verify compatibility for Y", never "bug: Y".
- **GitHub handoff:** close with an ordered path through the real PR: primary hunks first, then guardrails/tests, then
  supporting/mechanical files.
  This is the final product of the presentation.

## Introduced concepts: explain the business logic separately

Before Act I, the template has a **concept primer** plus fixed sidebars.
Use it for the concepts a reviewer must hold in working memory before the diff makes sense:

- **Left fixed sidebar:** one entry per introduced domain/concept layer, followed by story-section links for Act I-IV.
  Label concept entries with `domain -> layer -> concept`, not a file name.
- **Main concept primer:** one card per concept with the what/how/why triad:
  - **What** the domain concept means in product/user/system terms.
  - **How** this PR models, routes, validates, or changes it, with source anchors.
  - **Why** it matters for behavior, risk, or review attention.
- **Vertical anchor stack:** concept cards stay one per row.
  Do not put them in a multi-column grid: when two cards share the same vertical position,
  the second sidebar link appears to do nothing even if the hash changes.
- **Right fixed sidebar:** notes that would clutter the main column: caveats, glossary details, examples, non-obvious tradeoffs,
  migration constraints, reviewer shortcuts, or "watch this line" reminders.
  Notes follow both concept links and readiness/story links.
- **Business code rule:** any non-trivial product/domain logic must get a concept card unless it is already established project vocabulary.
  Do not make reviewers infer business semantics from symbol names alone.
- **No concept spam:** mechanical plumbing, generated code, pure style, and obvious tests do not become concepts.
  If the PR is purely mechanical, keep one explicit "No new business concepts" card and say which invariant or workflow is preserved.
- **Interactive preference:** when a concept has moving parts, prefer deterministic HTML flow nodes, toggles, cards, or
  simple CSS/JS animation.
  Use generated images only for broad flow/contrast ideas where exact labels are not load-bearing.

## The one law: one idea per beat, one primary medium per beat

The most common failure is **semantic triplication** — a paragraph says X, the image re-says X, the cards re-say X. Forbidden.

- Each beat delivers exactly **one** insight.
- Each beat has exactly **one primary medium**: a diagram **or** a diff — never both stacked saying the same thing.
- Prose is **connective tissue only**: it frames _why this beat matters_ or transitions to the next.
  It must never describe what the adjacent visual already shows.
- Pick the medium by the nature of the idea:
  - **Flow / contrast / state / "before→after"** → diagram is primary; text = one caption line + at most one "why it matters" line.
  - **The code itself is the point** → diff is primary; annotation = 1 short note per changed line-group. No diagram duplicating it.
  - **Exact labels / symbol lists / option names** → deterministic HTML flow, cards, or diff.
    Do not ask an image model to reproduce exact text unless the label count is tiny and the image is genuinely the fastest explanation.
- **Show the load-bearing line.** If the insight _is_ a specific line/option (a header set, a flag flipped, an arg threaded),
  that exact diff line MUST be visible in the beat.
  A diagram may set it up or contrast it, but must never _replace_ the code that is the point —
  otherwise the reader is told a line matters and never shown it.
  (This is why a "diagram-primary" beat for a one-line code insight is wrong: the medium doesn't fit the idea.)

## The 5-act spine (narrative, not file order)

Walking a file top-to-bottom is just "the PR, slower." Order by the _story_:

1. **Hero** — one-sentence thesis + the shape (flow diagram) + 3–4 invariant chips.
2. **Concept primer — introduced vocabulary.** The separate business/domain explanation layer.
   This is outside the 5-act spine so Act II can stay lean.
3. **Readiness map — review route.** Mental model, layers, topology, load-bearing lines, risk-attention map, and GitHub handoff.
   This makes the page useful for complex PRs, not just readable.
4. **Act I — Goal & the bet.** Why the PR exists + the single core mechanism change, as ONE contrast diagram.
   **No code yet** — establish the mental model.
5. **Act II — The load-bearing changes.** Only the **1–3** changes that actually carry risk/insight/security.
   Order them as a **causal chain**, not an unordered list:
   each beat should be a _consequence
   or obligation created by the previous one_ (e.g. "switching to the new transport is what _creates_ the framing problem the next beat solves").
   Each gets the medium that explains it fastest (medium chosen by the idea per the one law, not for visual rotation).
   Importance = how much room a beat gets.
   Split layout is rare: use it only when the diagram provides context and the diff is still the load-bearing medium.
   Never let "vary it" override medium-by-idea or drop a load-bearing line.
6. **Act III — Invariants held.** The "we didn't break X" reassurances, as a **compact card rail** (claim + one-line proof each),
   NOT full sections.
   This is where most dedup happens.
   At most one card carries a thumbnail.
7. **Act IV — Change map.** Every changed file/group by role.
   For one file it's short; for a 40-file PR this is what lets the reader skip what's mechanical.
8. **Footer — review handoff scorecard.** What was gained + what was kept, plus the exact order to open GitHub.

### Continuity: no teleports

The reader must **never** wonder "how did we get here?" — every beat is reached by a visible thread, not dropped in.

- **Between acts:** a **transition** — one big connective sentence with whitespace.
- **Between beats inside an act:** each beat opens with **one connective clause** that ties it to the previous beat or the goal —
  name the link before the new idea (e.g. "Routing through the new transport is exactly what breaks GET/DELETE framing —
  which is the next change.").
  A beat that introduces an idea with no bridge is a teleport; rewrite it or reorder the chain so the link is real.
- The chain is the test: read the act's beat openers in order with the visuals hidden.
  If it doesn't read as one argument, the ordering or the bridges are wrong — fix those before touching the visuals.

## Role classification (the engine that scales to many files)

Anchor the narrative to the **goal**, not the file list. Classify every hunk/file:

- **PRIMARY** — carries the goal or the main risk.
  Gets a full Act II beat (code or diagram).
  Cap at **3**.
  If you think you have 5 primaries, you haven't found the real goal yet — re-read the PR description.
- **SUPPORTING** — enables a primary (wiring, plumbing, a new param threaded through). Short beat or a ledger row.
- **GUARDRAIL** — tests, types, schema. Usually a ledger row; mention in Act III if a test _proves_ an invariant.
- **CLEANUP** — deletions, renames, mechanical moves. Ledger rows only.

Only PRIMARY (and occasionally SUPPORTING) earn beats.
Everything else folds into the Act IV ledger as one line each, preserving the role label.
That is the entire trick to keeping a big PR a focused narrative instead of a wall of diffs.

## Diffs: real, exact, trimmed

- Use the **actual diff** (`git diff <base>...HEAD -- <file>`), not paraphrased code.
- Trim long bodies with `…` and say so in the footer source note.
- Syntax tokens are CSS classes inside `<span class="s">`: `tok-k` (keyword), `tok-s` (string), `tok-c` (comment), `tok-f` (function),
  `tok-n` (number/bool).
- `ln add` / `ln del` / `ln ctx` set the line background and `+`/`-`/` ` gutter.
- HTML-escape `<`, `>`, `&` inside code (`&lt; &gt; &amp;`). This is the #1 source of a broken render — verify in a browser (see SKILL.md).

## Images via `,nano-banana` (see the nano-banana skill)

- Reserve diagrams for **goal-level flow/contrast** + **at most one additional state/flow idea**.
  Default to a single Act I diagram; you cannot (and must not) draw one diagram per file.
- Reference images by **relative filename** in the same dir as the HTML. Do NOT base64-inline them — it bloats the file and slows editing.
- Prompt for the house style every time so images cohere: `dark background #0b1020, thin teal/blue/amber line style,
developer documentation, labeled, no people`, plus the specific BEFORE/AFTER or state.
- **Verify each image by viewing it.** The model occasionally stutters text (e.g. "query.query.console") or adds a stray title banner.
  Regenerate if the most prominent images (Act I especially) have artifacts.
  Instruct "spell every label exactly once, no title banner" to reduce this.
- If a label-heavy image still has text artifacts after one regeneration, cut the image and represent the idea in HTML/diff instead.
  Accuracy beats visual variety.
- The CLI returns JPEG bytes even into a `.png` name — harmless for browsers.

## Act-rail (navigation)

- Labels can be **any length** — they wrap inside the left gutter when the Act rail is visible and hide below desktop widths,
  so never hand-tune widths per presentation.
  On wide screens the concept sidebar replaces the rail as the primary fixed navigation.
- One `<a>` per act; keep it to the 4 acts.

## Fixed sidebars

- The **left concept sidebar** is for domain/concept layers plus readiness/story-section navigation.
  It is not a table of contents for files; on wide screens it replaces the Act rail, so it must include the readiness map and Act I-IV links.
- The **right notes sidebar** is for compact supporting explanations tied to the active concept or readiness/story section.
  It should make the main column lighter, not become a second article.
- The **main column** remains the visual lane: concept primer cards, deterministic flows, real diffs, diagrams, and reveal animations.
- Concept cards must remain a vertical anchor stack so each left-sidebar concept block has a distinct scroll destination.
- On narrower screens, sidebars collapse away and the main concept cards remain the source of truth,
  so never put essential information only in a sidebar.
- Verify desktop geometry: left concept sidebar, main column, and
  right notes sidebar must not overlap at the browser width used for validation.

## Template shape

- The template is a scaffold, not a quota.
  Duplicate or delete beat/card/ledger/scorecard blocks to match the preflight before filling content.
- Fill or resize the concept primer, readiness map, concept sidebar links, story-section links, and notes sidebar before Act I.
  Every concept link must target a concept card, every readiness/story link must target its section, and
  every note card must be reachable from a sidebar link.
- Browser-verify every concept link, not just one: each link should change the hash, activate the matching note, and
  move the main column to a distinct concept-card position.
- Prefer targeted token replacement and block duplication/deletion over generating a complete HTML body from scratch;
  the latter commonly introduces escaped quotes and cleanup churn.
- Keep every changed file/group in exactly one Act IV ledger row. Use the role classes `primary`, `support`, `guardrail`, and `cleanup`.
- Delete unused optional blocks instead of leaving placeholder content hidden in the page.

## Voice

- Write for the **target reviewer's level** (e.g. a senior engineer of the relevant system).
  Use real symbol/API names.
  No dumbed-down analogies.
- For business/domain logic, make the semantics explicit before the mechanics: what changed for the user/system,
  how the PR represents it, and why the reviewer should care.
- Necessary detail, zero verbosity. Every line earns its place.
- The what/how/why triad is for **pivotal** hunks only — applying it to everything turns signal into noise. Some changes need only a "why".
