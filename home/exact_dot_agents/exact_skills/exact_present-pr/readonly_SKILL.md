---
name: present-pr
description: Build a self-contained scrollytelling HTML walkthrough of a PR (or a set of local changes) — goal-focused narrative, real diffs, generated diagrams — and open it in the user's browser.
disable-model-invocation: true
---

# PR presentation (scrollytelling HTML)

Turn a PR or a local diff into one **self-contained HTML page** the reviewer can scroll to understand the change _before_ opening the diff — at lower cognitive cost. Vanilla HTML/CSS/JS, no build, no CDN. Then open it in the browser.

This is not a code-review skill; it does not modify the repo under review.

## Bundled references (read before generating)

Deployed alongside this file:

- `~/.agents/skills/present-pr/references/template.html` — the **proven** scaffold. Copy it; fill `{{TOKENS}}`; never rewrite its CSS/JS.
- `~/.agents/skills/present-pr/references/authoring.md` — the design laws (5-act spine, beat-to-beat continuity, one-medium-per-beat dedup + show-the-load-bearing-line, role classification, image prompting, rail rules). Follow it; it is the difference between signal and a wall of text.

Read both fully before writing any HTML.

## Contract

- Input: a PR (via `gh`) or the current branch's local changes. The user may name a goal/thesis; if not, derive it from the PR description + diff and state it.
- Output: `<slug>-presentation.html` plus `nb-*.png` images, all in ONE output dir. Default output dir: `/tmp/present-pr/<repo>-<pr-or-branch>/`.
- End state: the page is opened in the user's default browser, and you report the file path + the goal/thesis you presented.
- You do **not** post anything, comment on the PR, or edit the reviewed repo.

## Workflow

### 1. Gather the change (evidence first)

- PR given: `gh pr view <n> --json title,body,files,baseRefName,headRefName` and `gh pr diff <n>` (or for the current branch, find the base with `git merge-base origin/<base> HEAD`, then `git diff <base>...HEAD`).
- Read the **actual** diff hunks for the files you will feature — paraphrased code is not allowed in beats.
- If you need base-branch context (existing behavior, conventions, related call sites) and the repo is indexed, use the `semantic-code-search` skill as _supporting_ context only — validate against the local diff.

### 2. Find the goal and classify every file

Per `authoring.md`:

- State the single **goal/thesis** in one sentence.
- Classify each changed file/hunk: PRIMARY (≤3) | SUPPORTING | GUARDRAIL | CLEANUP.
- Only PRIMARY (and key SUPPORTING) earn Act II beats; the rest become Act IV ledger rows. This is what keeps a large multi-file PR a focused narrative.

### 3. Plan the beats (one idea, one medium each — as a chain)

- Map the goal + classified changes onto the 5-act spine.
- **Order the Act II beats as a causal chain**, then write the one-line **bridge** for each seam (and between acts): the clause that says why this beat follows the last. Read the bridges in order with visuals hidden — they must form one argument with no teleports. If they don't, reorder or rewrite before generating anything.
- For each beat decide: **diagram-primary** or **diff-primary** (never both for the same idea), choosing the medium by the idea's nature — not to rotate layouts. If the insight is a specific line/option, the beat **must show that real diff line**; a diagram may augment but never replace it. Decide which 1–3 diagrams are worth generating.

### 4. Generate diagrams

- Create the output dir, `cd` into it.
- Use the `nano-banana` skill. House style every prompt: dark `#0b1020` background, thin teal/blue/amber line art, labeled, no people, no title banner, each label spelled exactly once. Write to `nb-<name>.png` in the output dir.
- **View each generated image** and regenerate any with text stutter/artifacts, especially the Act I hero diagram.

### 5. Fill the template

- Copy `template.html` to `<output>/<slug>-presentation.html`.
- Replace every `{{TOKEN}}`; use the beat blocks already present as patterns (add/remove change beats, invariant cards, ledger rows as needed).
- Reference images by **relative filename** only (same dir). Never base64-inline.
- HTML-escape `<`, `>`, `&` inside all code beats.

### 6. Verify in a real browser (mandatory)

A broken render is the default failure mode (unescaped code, a bad token, a missing image). Before opening for the user, verify with the `playwriter` skill:

- Serve the dir (`python3 -m http.server` in the output dir) and load it — `file://` is blocked in playwriter.
- Assert **zero** `pageerror`/`console.error`, all `nb-*.png` resolve (no 404s), the act-rail shows on scroll with floating labels not overlapping body text, and reveal animations fire. Fix and re-verify until clean.

### 7. Open for the user

- macOS: `open "<output>/<slug>-presentation.html"`. Report the absolute path and the goal/thesis you presented.

## Anti-patterns

- Walking the file top-to-bottom instead of telling the goal's story.
- A **teleporting beat** — introducing an idea with no bridge from the previous beat or the goal, so the reader can't tell how the narrator got there.
- **Replacing a load-bearing code line with only a diagram**, so the line that is the point (a header, a flag, an option) is named but never shown.
- Rotating mediums (diff → image → split) for variety instead of choosing each by the idea — it reads as inconsistency, not rhythm.
- Saying the same thing in prose **and** the image **and** a card (triplication).
- A diagram per file, or diagrams with stuttered/garbled labels.
- Rewriting the template's CSS/JS, or hand-tuning rail label widths.
- Paraphrased code instead of the real diff.
- Opening the page without a clean browser verification first.
