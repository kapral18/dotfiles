---
name: k-communication
description: "Use when drafting human-visible communication; apply canonical tone/style before external text."
---

# Communication (Centralized Tone & Style)

Owns wording of human-directed communication produced on the user's behalf, on any surface and in either direction;
examples below are non-exhaustive.

- **Proactive:** PR/issue descriptions, commit/release messages, announcements, status updates, a new comment that starts a thread.
- **In response:** replies to a comment/message/thread (see "When Responding To An Existing Message/Thread").

Surface-specific skills (`k-github`, `k-slack`, `k-google-workspace`, `k-review`, …) handle the _mechanics_ (which API/endpoint, anchoring, threading, formatting) and point here for _wording_.

Scope boundaries:

- This skill governs **wording of external human-visible content** only.
- **Whether and how to publish** (approval, bot-vs-human carve-out, draft → show payload → wait) is the Human-Visible Publication Gate in the SOP (`~/AGENTS.md`); do not restate or weaken it here.
- In-session chat/CLI responses follow `~/AGENTS.md` §8; this skill is for other humans.
- Load points: `k-compose-pr`, `k-compose-issue`, `k-git` (commit messages), `k-github`, `k-slack`, `k-google-workspace`, and `k-review` MUST load this skill before drafting.
  A draft that no side effect follows yet is still publication text; apply every rule to it.

## External register

Apply every rule before drafting text another human will read.
In-session `~/AGENTS.md` §8 shape rules do not override this skill's friendly register.
Load `~/.agents/skills/k-anti-slop/SKILL.md` and its prose reference for the wording filter;
reuse them if already loaded for this invocation.

- Match the surface's register; keep simple social replies in natural conversational phrasing, using lab-report phrasing only when requested.

## Core Tone

- Direct, friendly, polite. Plain language, no corporate filler.
- Stay collegial and neutral in every exchange; confrontational or accusatory wording is off limits.
  When something expected is missing or wrong, ask what's blocking it or state the issue neutrally, without fault or blame.
- Honest about epistemic state: separate observed (evidence) from inferred (hypothesis) from recommended (action).
  State certainty at its actual level.
- Apply `~/AGENTS.md` §2 when drafting agreement or disagreement: politeness must not imply that an unverified claim is correct.
  Give the supported reason, correction, or unresolved question; do not draft concessions or promises merely to placate the recipient.
- Keep session provenance out of external text: do not narrate the assistant, its workflow, tool calls, or errors encountered while drafting.
  Preserve legitimate domain facts, including tool, harness, model, and API names when they are the subject being discussed.
  Exception: a verified domain overlay may mandate AI-attribution trailers; it overrides this rule for the surfaces it names.
- Session-only artifacts MUST NOT appear in external text: internal rule citations, task/worker IDs, `Unknown because` markers, handoff paths or contents, hook notes, and worker status reports.
  Strip these provenance details before showing the draft; do not strip a required domain term or report field merely because the session also uses it.

## Concision

Length follows the budget for the artifact class.
"Concise" means unpadded, not shallow: if a cut removes a fact, real hedge, or safety qualifier, restore it and cut elsewhere.

Budgets (words of narrative; code blocks and links do not count):

- Thread reply, chat message, ack: ≤40.
- PR/issue comment, review reply: ≤80.
- PR description, issue body, release note: ≤200 + optional short bullet list.

- Every sentence carries a fact, request, or decision. Delete the rest.
- Cut anything the reader infers from context (thread, diff, prior message, PR title).
  Do not restate the concern, file path, obvious effect, or what the reader just said.
- Prefer no message over a low-signal message.
  Do not draft a reply that only repeats the thread, adds attribution trivia, or turns a casual exchange into an investigation report.
- No headline summaries, status prefixes, or `RE:`-style headers. Get to the substance.
- Prefer the shortest form that carries full meaning: a one-line comment, a tight PR description, a single-sentence status update.
- PR review summary bodies are short acknowledgements: prefer `Looks good.` for clean approvals and `Left inline feedback.` when comments exist.
  Do not repeat the inline findings.

## Default Shape

Lead with the point; add uncertainty or a question only when relevant:

1. **The point**, in the first sentence: what changed, what you're asking, or what you found.
2. **The doubt**, when one exists: the assumption you're unsure of, or what you could not verify. One clause, stated plainly.
3. **A request**, when the recipient has something to decide or do.

Add sections only when the content needs them.

- Keep each paragraph or bullet on one topic; related facts may share a sentence.
- Keep references beside the claims they support. Put long or copyable commands on separate lines when that improves use.
- Argue from the technical reason or the open question, never from time or effort ("didn't have time to", "for now", "quick fix" are all off limits).

## Structure (Longer-Form Artifacts)

For PR/issue descriptions, release notes, or multi-point messages, use the shortest complete structure.
Reach for a density primitive before prose; add sections only when a shorter form cannot carry their information:

- **Verdict line** for status / decision / ack.
- **Bulleted anchor list** for a set of findings, changes, or asks — one clause per bullet with a link/anchor.
- **Short table** for comparisons or before/after (≤5 columns).
- **`## Summary` / `## Why`** only when the content genuinely needs sections.

- Lead with what changed / what's being asked; rationale and detail after.
- Drop bullets that restate each other or the section heading.
- A later section may not restate an item already given in an earlier list; refer by name and add only new information.

## References To Code / Commits / Artifacts

- Reference, don't re-explain: when work landed elsewhere, link to the canonical commit/thread/message/issue rather than restating it.
- On GitHub specifically, code/file/symbol references and commit references must be clickable links (exact source on head SHA;
  full commit URL — never a bare hash). See the `k-github` / `k-review` skills for the exact link forms.

## When Responding To An Existing Message/Thread

Before drafting a response to an existing message or thread, MUST load and follow `~/.agents/skills/k-communication/references/thread-replies.md`.
Verify the current outcome before choosing reply or resolution-state wording.
