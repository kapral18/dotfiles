# Authoring rules — PR presentation

These are the design laws the template encodes. The presentation exists to let a reviewer **get the accurate, detailed picture before opening the diff**, at lower cognitive cost. If a choice doesn't serve that, cut it.

## The one law: one idea per beat, one primary medium per beat

The most common failure is **semantic triplication** — a paragraph says X, the image re-says X, the cards re-say X. Forbidden.

- Each beat delivers exactly **one** insight.
- Each beat has exactly **one primary medium**: a diagram **or** a diff — never both stacked saying the same thing.
- Prose is **connective tissue only**: it frames _why this beat matters_ or transitions to the next. It must never describe what the adjacent visual already shows.
- Pick the medium by the nature of the idea:
  - **Flow / contrast / state / "before→after"** → diagram is primary; text = one caption line + at most one "why it matters" line.
  - **The code itself is the point** → diff is primary; annotation = 1 short note per changed line-group. No diagram duplicating it.
- **Show the load-bearing line.** If the insight _is_ a specific line/option (a header set, a flag flipped, an arg threaded), that exact diff line MUST be visible in the beat. A diagram may set it up or contrast it, but must never _replace_ the code that is the point — otherwise the reader is told a line matters and never shown it. (This is why a "diagram-primary" beat for a one-line code insight is wrong: the medium doesn't fit the idea.)

## The 5-act spine (narrative, not file order)

Walking a file top-to-bottom is just "the PR, slower." Order by the _story_:

1. **Hero** — one-sentence thesis + the shape (flow diagram) + 3–4 invariant chips.
2. **Act I — Goal & the bet.** Why the PR exists + the single core mechanism change, as ONE contrast diagram. **No code yet** — establish the mental model.
3. **Act II — The load-bearing changes.** Only the **1–3** changes that actually carry risk/insight/security. Order them as a **causal chain**, not an unordered list: each beat should be a _consequence or obligation created by the previous one_ (e.g. "switching to the new transport is what _creates_ the framing problem the next beat solves"). Each gets the medium that explains it fastest (medium chosen by the idea per the one law, not for visual rotation). Importance = how much room a beat gets. Layout may vary (code/diagram/split) only as a tiebreaker — never let "vary it" override medium-by-idea or drop a load-bearing line.
4. **Act III — Invariants held.** The "we didn't break X" reassurances, as a **compact card rail** (claim + one-line proof each), NOT full sections. This is where most dedup happens. At most one card carries a thumbnail.
5. **Act IV — Change map.** Every changed file/group by role. For one file it's short; for a 40-file PR this is what lets the reader skip what's mechanical.
6. **Footer — outcome scorecard.** What was gained + what was kept, each with its exact mechanism.

### Continuity: no teleports

The reader must **never** wonder "how did we get here?" — every beat is reached by a visible thread, not dropped in.

- **Between acts:** a **transition** — one big connective sentence with whitespace.
- **Between beats inside an act:** each beat opens with **one connective clause** that ties it to the previous beat or the goal — name the link before the new idea (e.g. "Routing through the new transport is exactly what breaks GET/DELETE framing — which is the next change."). A beat that introduces an idea with no bridge is a teleport; rewrite it or reorder the chain so the link is real.
- The chain is the test: read the act's beat openers in order with the visuals hidden. If it doesn't read as one argument, the ordering or the bridges are wrong — fix those before touching the visuals.

## Role classification (the engine that scales to many files)

Anchor the narrative to the **goal**, not the file list. Classify every hunk/file:

- **PRIMARY** — carries the goal or the main risk. Gets a full Act II beat (code or diagram). Cap at **3**. If you think you have 5 primaries, you haven't found the real goal yet — re-read the PR description.
- **SUPPORTING** — enables a primary (wiring, plumbing, a new param threaded through). Short beat or a ledger row.
- **GUARDRAIL** — tests, types, schema. Usually a ledger row; mention in Act III if a test _proves_ an invariant.
- **CLEANUP** — deletions, renames, mechanical moves. Ledger rows only.

Only PRIMARY (and occasionally SUPPORTING) earn beats. Everything else folds into the Act IV ledger as one line each. That is the entire trick to keeping a big PR a focused narrative instead of a wall of diffs.

## Diffs: real, exact, trimmed

- Use the **actual diff** (`git diff <base>...HEAD -- <file>`), not paraphrased code.
- Trim long bodies with `…` and say so in the footer source note.
- Syntax tokens are CSS classes inside `<span class="s">`: `tok-k` (keyword), `tok-s` (string), `tok-c` (comment), `tok-f` (function), `tok-n` (number/bool).
- `ln add` / `ln del` / `ln ctx` set the line background and `+`/`-`/` ` gutter.
- HTML-escape `<`, `>`, `&` inside code (`&lt; &gt; &amp;`). This is the #1 source of a broken render — verify in a browser (see SKILL.md).

## Images via `,nano-banana` (see the nano-banana skill)

- Reserve diagrams for **goal-level flow/contrast** + **at most one per PRIMARY change**. You cannot (and must not) draw one diagram per file.
- Reference images by **relative filename** in the same dir as the HTML. Do NOT base64-inline them — it bloats the file and slows editing.
- Prompt for the house style every time so images cohere: `dark background #0b1020, thin teal/blue/amber line style, developer documentation, labeled, no people`, plus the specific BEFORE/AFTER or state.
- **Verify each image by viewing it.** The model occasionally stutters text (e.g. "query.query.console") or adds a stray title banner. Regenerate if the most prominent images (Act I especially) have artifacts. Instruct "spell every label exactly once, no title banner" to reduce this.
- The CLI returns JPEG bytes even into a `.png` name — harmless for browsers.

## Act-rail (navigation)

- Labels can be **any length** — they render as solid floating popovers, so never hand-tune widths or content-aware breakpoints. The template already does this correctly; do not reintroduce gutter-width math.
- One `<a>` per act; keep it to the 4 acts.

## Voice

- Write for the **target reviewer's level** (e.g. a senior engineer of the relevant system). Use real symbol/API names. No dumbed-down analogies.
- Necessary detail, zero verbosity. Every line earns its place.
- The what/how/why triad is for **pivotal** hunks only — applying it to everything turns signal into noise. Some changes need only a "why".
