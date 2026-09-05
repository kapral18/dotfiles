---
name: k-present-pr
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

- `~/.agents/skills/k-present-pr/references/template.html` — the **proven** scaffold.
  Use the bundled `scripts/template.py` to copy its fixed CSS/JS; never rewrite its CSS/JS.
- `~/.agents/skills/k-present-pr/references/authoring.md` — the design laws.
  It covers the review-readiness map, introduced-concepts primer, 5-act spine, fixed concept/notes sidebars, beat-to-beat continuity, one-medium-per-beat dedup, show-the-load-bearing-line, role classification, image prompting, and rail rules.
  Follow it; it is the difference between signal and a wall of text.

Read `authoring.md` fully before writing any HTML.
Create the output directory, then run `python3 ~/.agents/skills/k-present-pr/scripts/template.py prepare ~/.agents/skills/k-present-pr/references/template.html <output>/<slug>.content.html`.
Read the entire prepared `.content.html` before editing it; it contains all editable markup and template instructions.
The helper reads the complete template and replaces only its fixed CSS/JS with reserved markers; do not alter those markers.

## Contract

- Input: a PR (via `gh`) or the current branch's local changes.
  The user may name a goal/thesis; if not, derive it from the PR description + diff and state it.
- Output: `<slug>-presentation.html` plus `nb-*.png` images, all in ONE output dir.
  Default output dir: `/tmp/present-pr/<repo>-<pr-or-branch>/`.
- Page shape: fixed left sidebar = introduced concepts by concept area/layer plus readiness/story navigation;
  main area = review-readiness map, visual story, diffs, diagrams, and animation;
  fixed right sidebar = overflow notes that follow the active concept or readiness/story section without crowding the main narrative.
- End state: the page is opened in the user's default browser, and you report the file path + the goal/thesis you presented.
- Your side effects end at the local page: leave the PR uncommented, publish nothing, and keep the reviewed repo unedited.

Repo/org-specific overlays:

- A domain overlay is a repo/org-specific skill selected from the verified target repo/org, not guessed from wording.
  It may add safe handling for repo-specific CI/build metadata.
- Current concrete overlay: for Elastic Buildkite/CI links, load `~/.agents/skills/k-elastic-domain/SKILL.md`, then use the `k-buildkite` skill (`bk` CLI).

## Workflow

### 0. Fast path and token budget

- If `/tmp/specs/<pwd>/` or `/tmp/present-pr/<repo>-<pr-or-branch>/` already contains evidence for the same PR/head SHA, reuse it after verifying the head SHA still matches.
  Refresh only PR metadata/comments that may have changed.
- When this turn names Nano Banana, Gemini image, or Google image gen/edit, the default diagram budget is **one generated image** for the Act I goal-level contrast.
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
    For Elastic Buildkite, load `k-elastic-domain`, then use the `k-buildkite` skill (`bk` CLI).
- Read the **actual** diff hunks for the files you will feature — beats must contain real diff text, never paraphrased code.
- If you need base-branch context (existing behavior, conventions, related call sites) and the repo is indexed, use the `k-semantic-code-search` skill as _supporting_ context only — validate against the local diff.

### 2. Build the review model and classify every file

Apply `authoring.md`'s Review-readiness map, Introduced concepts, and Role classification sections in full.
State the single goal/thesis in one sentence; include the intended review posture in the mental model.
For each introduced concept, record what the reviewer must understand first and its supporting right-sidebar note.
For a PR with no new domain concepts, keep one explicit no-new-concepts entry explaining its mechanical/plumbing scope and preserved invariant/workflow.
Complete the readiness map, introduced-concepts inventory, what/how/why explanations, and every changed file/hunk's role before planning beats.

### 3. Plan the beats (one idea, one medium each — as a chain)

- Map the goal + classified changes onto the 5-act spine.
- Before touching HTML, write the full **authoring preflight** from `authoring.md` in your notes.
  Include concept area/layer/name, exact image filenames, invariant cards, scorecard claims, and the command-output budget alongside its required fields.
- **Order the Act II beats as a causal chain**, then write the one-line **bridge** for each seam (and between acts):
  the clause that says why this beat follows the last.
  Read the bridges in order with visuals hidden — they must form one argument with no teleports.
  If they don't, reorder or rewrite before generating anything.
- For each beat decide: **diagram-primary** or **diff-primary** (never both for the same idea).
  Choose the medium by the idea's nature, not to rotate layouts.
  If the insight is a specific line/option, the beat **must show that real diff line**;
  a diagram may augment it but the diff line stays visible. Decide which 0–2 diagrams are worth generating; default to 1.

### 4. Generate diagrams

- Create the output dir, `cd` into it.
- Default to deterministic HTML/diff for Act I/II visuals.
  Load `k-nano-banana` only if this turn named Nano Banana, Gemini image, or Google image gen/edit.
- When that named lane is in play: house style every prompt (dark `#0b1020` background, thin teal/blue/amber line art, labeled, no people, no title banner, each label spelled exactly once) and write `nb-<name>.png` in the output dir.
  View each generated image and regenerate any with text stutter/artifacts, especially the Act I hero diagram.
  If an image has repeated/misspelled labels after one regeneration, delete it and replace that idea with deterministic HTML/diff.
  Do not spend more attempts on label-heavy diagrams.

### 5. Fill the template

- Edit the prepared `<output>/<slug>.content.html`.
- Apply `authoring.md`'s Template shape and Fixed sidebars rules: resize to the preflight and fill the concept primer, readiness map, and both sidebars before Act I/II.
  Keep readiness sections as structured artifacts: layered-map, topology, and load-bearing-line rows, risk-attention cards, and an ordered GitHub handoff.
- Replace every placeholder token; use the beat blocks already present as patterns (add/remove change beats, invariant cards, ledger rows as needed).
- Reference images by **relative filename** only (same dir). Never base64-inline.
- HTML-escape `<`, `>`, `&` inside all code beats.
- Prefer template-token replacement or targeted block edits over regenerating a whole HTML body from scratch.
  Whole-body generation tends to introduce quote escaping and dropped-block cleanup loops.
- Run `python3 ~/.agents/skills/k-present-pr/scripts/template.py render ~/.agents/skills/k-present-pr/references/template.html <output>/<slug>.content.html <output>/<slug>-presentation.html` to restore the exact fixed CSS/JS.
  After further content edits, render again. Do not open or verify the unassembled `.content.html` as the presentation.
- Run cheap static checks on the rendered presentation before browser verification:
  - placeholder check must target real template tokens only, e.g. `\{\{[A-Z0-9_]+\}\}`;
    grep for that token shape rather than generic braces, because the template contains normal CSS/JS braces.
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
  - every insight that is a specific source line/option shows that exact diff line in its beat,
  - no beat repeats the same idea in prose + visual + card.

### 6. Verify in a real browser (mandatory)

A broken render is the default failure mode (unescaped code, a bad token, a missing image).
Before opening for the user, verify with the `k-playwriter` skill:

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
