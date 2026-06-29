---
name: present-pr
description: Build and open a self-contained HTML walkthrough that makes a PR review-ready.
disable-model-invocation: true
---

# PR presentation (scrollytelling HTML)

Turn a PR or a local diff into one **self-contained HTML page** the reviewer can scroll to understand the change _before_ opening the diff —
at lower cognitive cost. The page is a **review-readiness map**, not a review.
It explicitly explains PR-introduced concepts, maps system layers and change topology, indexes load-bearing lines, and names risk areas without judging them.
The final handoff tells the reviewer how to open GitHub with confidence. Vanilla HTML/CSS/JS, no build, no CDN. Then open it in the browser.

This is not a code-review skill; it does not modify the repo under review.

## Bundled references (read before generating)

Deployed alongside this file:

- `~/.agents/skills/present-pr/references/template.html` — the **proven** scaffold.
  Copy it; fill the placeholder tokens; never rewrite its CSS/JS.
- `~/.agents/skills/present-pr/references/authoring.md` — the design laws.
  It covers the review-readiness map, introduced-concepts primer, 5-act spine, fixed concept/notes sidebars, beat-to-beat continuity, one-medium-per-beat dedup, show-the-load-bearing-line, role classification, image prompting, and rail rules.
  Follow it; it is the difference between signal and a wall of text.

Read both fully before writing any HTML.

## Contract

- Input: a PR (via `gh`) or the current branch's local changes.
  The user may name a goal/thesis; if not, derive it from the PR description + diff and state it.
- Output: `<slug>-presentation.html` plus `nb-*.png` images, all in ONE output dir.
  Default output dir: `/tmp/present-pr/<repo>-<pr-or-branch>/`.
- Page shape: fixed left sidebar = introduced concepts by concept area/layer plus readiness/story navigation;
  main area = review-readiness map, visual story, diffs, diagrams, and animation;
  fixed right sidebar = overflow notes that follow the active concept or readiness/story section without crowding the main narrative.
- End state: the page is opened in the user's default browser, and you report the file path + the goal/thesis you presented.
- You do **not** post anything, comment on the PR, or edit the reviewed repo.

Repo/org-specific overlays:

- A domain overlay is a repo/org-specific skill selected from the verified target repo/org, not guessed from wording.
  It may add safe handling for repo-specific CI/build metadata.
- Current concrete overlay: for Elastic Buildkite/CI links, load `~/.agents/skills/elastic-domain/SKILL.md`, then use the `buildkite` skill (`bk` CLI).

## Workflow

### 0. Fast path and token budget

- If `/tmp/specs/<pwd>/` or `/tmp/present-pr/<repo>-<pr-or-branch>/` already contains evidence for the same PR/head SHA, reuse it after verifying the head SHA still matches.
  Refresh only PR metadata/comments that may have changed.
- Default diagram budget: **one generated image** for the Act I goal-level contrast.
  Add a second only when the preflight proves it carries a distinct flow/state idea.
  Do not generate images for exact labels, symbol lists, or code-line insights; use HTML flow nodes, cards, or diff beats instead.
- For repo-specific CI/build links, load the verified overlay and fetch only the compact facts needed for the story.
  Do not dump full build metadata unless CI is itself the presentation thesis.
- Prefer deterministic HTML/CSS/code beats over generated images for label-heavy visuals.
  Generated diagrams often stutter labels; exact labels and exact source lines belong in the HTML.
- Keep command output compact. Save large raw evidence to files, then extract only the lines needed for the preflight and beats.

### 1. Gather the change (evidence first)

- PR given: `gh pr view <n> --json title,body,files,baseRefName,headRefName,closingIssuesReferences,comments,reviews` and `gh pr diff <n>` (or for the current branch, find the base with `git merge-base origin/<base> HEAD`, then `git diff <base>...HEAD`).
- When a PR is given, investigate it exhaustively before fixing the goal/thesis —
  the real "why" usually lives in the discussion, not the description. Read everything, all the way down:
  - the full PR body and every conversation comment (`gh pr view <n> --comments`),
  - every review and inline review-thread comment (`gh api --paginate repos/OWNER/REPO/pulls/<n>/reviews` and `.../pulls/<n>/comments`),
  - every linked/closing issue and all of its comments (`gh issue view <m> --comments`), and any PR/issue referenced transitively in the body, comments, or reviews — recurse until no new reference adds context.
  - For repo-specific CI/build links, do not fetch directly unless the verified overlay says it is safe.
    For Elastic Buildkite, load `elastic-domain`, then use the `buildkite` skill (`bk` CLI).
- Read the **actual** diff hunks for the files you will feature — paraphrased code is not allowed in beats.
- If you need base-branch context (existing behavior, conventions, related call sites) and the repo is indexed, use the `semantic-code-search` skill as _supporting_ context only — validate against the local diff.

### 2. Find the goal, readiness map, introduced concepts, and classify every file

Per `authoring.md`:

- State the single **goal/thesis** in one sentence.
- Build a **review-readiness map** before writing the story:
  - mental model: before/after behavior, why now, and the review posture this page should create,
  - layered explanation: business concept -> domain/data shape -> API/contract -> state/flow -> UI/runtime -> tests/guardrails,
  - change topology: responsibility groups, files in each group, and how groups depend on each other,
  - load-bearing line index: exact hunks/lines that deserve reviewer attention and why,
  - invariants/non-changes: what the PR intentionally preserves,
  - risk-attention map: areas to inspect later in GitHub, phrased as "check this" not "this is wrong",
  - GitHub handoff order: primary hunks first, guardrails second, mechanical files last.
- Build an **introduced concepts inventory** before writing beats.
  Include each business/domain concept, the layer it belongs to, the source anchors that introduced it, what a reviewer must understand first, and which right-sidebar note supports it.
  If a PR introduces no new domain concept, write a single "no new concepts" entry explaining that the change is mechanical/plumbing.
- Explain business code through the **what/how/why triad**.
  Cover what the domain concept means, how the PR models or changes it, and why that matters to product/user/system behavior.
  Keep it accurate, source-anchored, and cognitively accessible without dumbing down symbol/API names.
- Classify each changed file/hunk: PRIMARY (≤3) | SUPPORTING | GUARDRAIL | CLEANUP.
- Only PRIMARY (and key SUPPORTING) earn Act II beats; the rest become Act IV ledger rows.
  This is what keeps a large multi-file PR a focused narrative.

### 3. Plan the beats (one idea, one medium each — as a chain)

- Map the goal + classified changes onto the 5-act spine.
- Before touching the HTML, write a compact **authoring preflight** in your notes:
  - goal/thesis + target reviewer,
  - evidence cache status (new vs reused, PR/head SHA, refreshed sources),
  - review-readiness map: mental model, layered explanation, topology groups, load-bearing line index, invariants/non-changes, risk-attention map, and GitHub handoff order,
  - introduced concepts inventory: concept area/layer/name, what/how/why, source anchors, left-sidebar label, right-sidebar note, and best teaching medium,
  - every changed file/hunk with role, source anchor, and why it matters,
  - Act II beats in order, each with its bridge from the previous beat,
  - primary medium per beat (`diagram` or `diff`) and the exact source line/image each beat needs,
  - ledger rows, invariant cards, scorecard claims, image filenames, verification checks, and command-output budget.
- **Order the Act II beats as a causal chain**, then write the one-line **bridge** for each seam (and between acts):
  the clause that says why this beat follows the last.
  Read the bridges in order with visuals hidden — they must form one argument with no teleports.
  If they don't, reorder or rewrite before generating anything.
- For each beat decide: **diagram-primary** or **diff-primary** (never both for the same idea).
  Choose the medium by the idea's nature, not to rotate layouts.
  If the insight is a specific line/option, the beat **must show that real diff line**; a diagram may augment but never replace it.
  Decide which 0–2 diagrams are worth generating; default to 1.

### 4. Generate diagrams

- Create the output dir, `cd` into it.
- Use the `nano-banana` skill.
  House style every prompt: dark `#0b1020` background, thin teal/blue/amber line art, labeled, no people, no title banner, each label spelled exactly once.
  Write to `nb-<name>.png` in the output dir.
- **View each generated image** and regenerate any with text stutter/artifacts, especially the Act I hero diagram.
- If an image has repeated/misspelled labels after one regeneration, delete it and replace that idea with deterministic HTML/diff content.
  Do not spend more attempts on label-heavy diagrams.

### 5. Fill the template

- Copy `template.html` to `<output>/<slug>-presentation.html`.
- First resize the content blocks to match the preflight: remove unused concept cards, sidebar notes, sample beats/cards/rows and duplicate only the blocks the story needs.
- Fill the concept primer, review-readiness map, and both sidebars before Act I/II beats.
  The left sidebar must name each introduced concept by concept area/layer and include the readiness map plus Act I-IV story links;
  the main concept cards must explain what/how/why; the right sidebar must hold clarifying notes, caveats, examples, or reviewer shortcuts for the active concept or story section that would otherwise clutter the main story.
- Keep concept cards in a vertical anchor stack, not a multi-column grid.
  Every concept sidebar block must visibly navigate to its own main-card position;
  two concepts sharing the same row makes the second link feel like a no-op.
- Fill the readiness sections as structured artifacts, not prose dumps: layered map rows, topology rows, load-bearing-line rows, risk-attention cards, and an ordered GitHub handoff.
- Replace every placeholder token; use the beat blocks already present as patterns (add/remove change beats, invariant cards, ledger rows as needed).
- Reference images by **relative filename** only (same dir). Never base64-inline.
- HTML-escape `<`, `>`, `&` inside all code beats.
- Prefer template-token replacement or targeted block edits over regenerating a whole HTML body from scratch.
  Whole-body generation tends to introduce quote escaping and dropped-block cleanup loops.
- Run cheap static checks before browser verification:
  - placeholder check must target real template tokens only, e.g. `\{\{[A-Z0-9_]+\}\}`;
    do **not** grep for generic braces because the template contains normal CSS/JS braces.
  - every changed file/group appears exactly once in the ledger,
  - every introduced concept appears once in the concept primer and once in the left sidebar,
  - every readiness section appears once and its links/anchors are reachable,
  - every load-bearing line in the index appears in an Act II diff beat or is explicitly marked as ledger-only,
  - every risk-attention item points to the layer/file group it concerns and avoids making a review finding,
  - every concept sidebar block changes hash, activates its matching note, and scrolls to a distinct concept-card position,
  - the readiness map and every Act I-IV section are reachable from the left sidebar on wide layouts;
    the act rail fallback remains usable on narrower layouts,
  - every sidebar note is reachable from a concept or readiness/story link and has a source/caveat anchor,
  - each referenced `nb-*` image exists and no unreferenced `nb-*` image remains in the output dir,
  - every load-bearing source line appears in a diff beat,
  - no beat repeats the same idea in prose + visual + card.

### 6. Verify in a real browser (mandatory)

A broken render is the default failure mode (unescaped code, a bad token, a missing image).
Before opening for the user, verify with the `playwriter` skill:

- Serve the dir over HTTP and load it — `file://` is blocked in playwriter.
  Start the server with deterministic cleanup, for example: `python3 -m http.server "$PORT" --bind 127.0.0.1 & echo $! > "$output/.server.pid"`.
- Use compact Playwriter assertions first.
  Print terse JSON for: page errors, console errors, failed local responses, image load status, placeholder presence, reveal counts, concept/sidebar geometry, rail fallback visibility, and concept-note state.
  Use snapshots only on failure or with a tight `search` filter.
- Assert **zero** `pageerror`/`console.error`, all `nb-*.png` resolve (no 404s), the left concept sidebar and right notes sidebar do not overlap the main column on wide desktop widths, the act-rail fallback remains usable when sidebars collapse, concept-note interactions work, and reveal animations fire.
  Fix and re-verify until clean.
- Stop the exact server PID or exact listening port after verification; do not use broad process-kill commands or large session listings to find it.

### 7. Open for the user

- macOS: `open "<output>/<slug>-presentation.html"`. Report the absolute path and the goal/thesis you presented.

## Anti-patterns

- Walking the file top-to-bottom instead of telling the goal's story.
- Letting introduced domain/business concepts appear only inside diff annotations instead of giving them a separate concept primer + sidebar entry.
- Explaining business code only as symbol mechanics without what/how/why and reviewer-visible behavior.
- Making the page feel like a review verdict. Risk items are "inspect this later", not findings.
- Ending without a GitHub handoff order; the reviewer should know exactly what to open first.
- Listing files without topology: reviewers need responsibility groups and dependencies, not just paths.
- A **teleporting beat** — introducing an idea with no bridge from the previous beat or the goal, so the reader can't tell how the narrator got there.
- **Replacing a load-bearing code line with only a diagram**, so the line that is the point (a header, a flag, an option) is named but never shown.
- Rotating mediums (diff → image → split) for variety instead of choosing each by the idea — it reads as inconsistency, not rhythm.
- Saying the same thing in prose **and** the image **and** a card (triplication).
- A diagram per file, or diagrams with stuttered/garbled labels.
- Multiple generated attempts for an exact-label diagram when a deterministic HTML beat would be faster and more accurate.
- Dumping full CI/build metadata into the conversation when the presentation only needs current/pass/fail context.
- Broad placeholder grep patterns that match CSS/JS braces.
- Rewriting the template's CSS/JS, or hand-tuning rail label widths.
- Paraphrased code instead of the real diff.
- Opening the page without a clean browser verification first.
