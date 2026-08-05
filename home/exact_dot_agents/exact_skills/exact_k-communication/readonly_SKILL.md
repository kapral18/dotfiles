---
name: k-communication
description: "Use when drafting human-visible communication; apply canonical tone/style before external text."
---

# Communication (Centralized Tone & Style)

Single source of truth for **how to word** any human-directed communication produced on the user's behalf, on **any** surface and in either direction.
The surfaces named below are examples, not an exhaustive list — this applies to any channel where a human reads what you wrote.

- **Proactive:** PR/issue descriptions, commit/release messages, announcements, status updates, a new comment that starts a thread.
- **In response:** replies to a comment/message/thread (see "When Responding To An Existing Message/Thread").

Surface-specific skills (`k-github`, `k-google-workspace`, `k-review`, `babysit`, …) handle the _mechanics_ (which API/endpoint, anchoring, threading, formatting) and point here for _wording_.

Scope boundaries:

- This skill governs **wording of external human-visible content** only.
- **Whether and how to publish** (approval, bot-vs-human carve-out, draft → show payload → wait) is the Human-Visible Publication Gate in the SOP (`~/AGENTS.md`); do not restate or weaken it here.
- **How the agent talks to the user in-session** (chat/CLI responses) is SOP §6 Communication;
  this skill is for content the agent emits to _other_ humans.

## Core Tone

- Direct, friendly, polite. Plain language, no corporate filler.
- Never confrontational or accusatory.
  When something expected is missing or wrong, ask what's blocking it or state the issue neutrally — never imply fault or assign blame.
- Honest about epistemic state: separate observed (evidence) from inferred (hypothesis) from recommended (action).
  Do not overstate certainty.
- Don't leak the AI/agentic session itself.
  The reader must not be able to tell an agent produced this: no mention of the agent/assistant, the skills/prompts/SOP it follows, the tools or CLIs it ran, request payloads, or the raw tool errors it hit while working.
  Write as the user would (e.g. not "my agent re-ran the `gh` call after a 422" — just make the point).
  It hides agentic plumbing; it does not withhold legitimate domain content like real API error codes the human needs.
  Exception: a verified domain overlay may mandate AI-attribution trailers; it overrides this rule for the surfaces it names.

## Concision

Length is a hard budget per artifact class, not a vibe.
"Concise" means unpadded, not shallow: if a cut removes a fact, real hedge, or safety qualifier, restore it and cut elsewhere.

Budgets (words of narrative; code blocks and links do not count):

- Thread reply, chat message, ack: ≤40.
- PR/issue comment, review reply: ≤80.
- PR description, issue body, release note: ≤200 + optional short bullet list.

- No water. Every sentence carries a fact, request, or decision. Delete the rest.
- Cut anything the reader infers from context (thread, diff, prior message, PR title).
  Do not restate the concern, file path, obvious effect, or what the reader just said.
- Prefer no message over a low-signal message.
  If the thread already has the correction or next step, and the only remaining contribution is historical color, attribution cleanup, or rephrasing someone else's point, do not draft.
- No headline summaries, status prefixes, or `RE:`-style headers. Get to the substance.
- Prefer the shortest form that carries full meaning: a one-line comment, a tight PR description, a single-sentence status update.
- PR review summary bodies describe inline topics, not commands: prefer `Left inline comments on <topics>.`

## Default Shape

For most messages, this covers it:

1. **The point**, in the first sentence: what changed, what you're asking, or what you found.
2. **The doubt**, when one exists: the assumption you're unsure of, or what you could not verify. One clause, stated plainly.
3. **The close**: `wdyt` / `lmk` / a short question.

That is the whole message. Add sections only when the content genuinely needs them.

- One idea per bullet or line. Split any sentence carrying two facts.
- Put paths, commands, IDs, and links on their own line, not buried mid-sentence.
- Never use time or effort as an argument ("didn't have time to", "for now", "quick fix").
  State the technical reason, or state the open question.

## Structure (Longer-Form Artifacts)

Brevity outranks structure here too: the shortest form that carries the full meaning wins.
For PR/issue descriptions, release notes, or any multi-point message, structure must earn its space —
reach for a density primitive before prose, and never add sections to fill a template:

- **Verdict line** for status / decision / ack.
- **Bulleted anchor list** for a set of findings, changes, or asks — one clause per bullet with a link/anchor.
- **Short table** for comparisons or before/after (≤5 columns).
- **`## Summary` / `## Why`** only when the content genuinely needs sections.

- Lead with what changed / what's being asked; rationale and detail after.
- One idea per bullet. Drop bullets that restate each other or the section heading.
- A later section may not restate an item already given in an earlier list; refer by name and add only new information.

## References To Code / Commits / Artifacts

- Reference, don't re-explain: when work landed elsewhere, link to the canonical commit/thread/message/issue rather than restating it.
- On GitHub specifically, code/file/symbol references and commit references must be clickable links (exact source on head SHA;
  full commit URL — never a bare hash). See the `k-github` / `k-review` skills for the exact link forms.

## When Responding To An Existing Message/Thread

Reply mechanics (in addition to everything above):

- Reply directly; do not quote the whole message.
  If you must reference a fragment, quote only the minimum needed (one short blockquote), then reply. Avoid email-style interleaved quoting.
- Replying to a reviewer's finding on the user's work: acknowledge, state what changed (link the fix commit), name the verification done, ask for re-review.
  Do not explain the reviewer's own domain or how the system they flagged works back at them — they found the issue;
  skip the mechanism lecture unless they ask.
- Match the existing register.
  For Slack or casual threads, do not write like a report: avoid phrases such as "I checked the history around the hypothesis" when "I had a quick look" or no reply would be more natural.

Triage outcome — when reacting to how the other party handled a request/thread, verify the outcome against the current state first (code/head, doc, message) — act on what is actually there, not on what was claimed.
Then reply by outcome:

- **Addressed** (verified, not merely claimed): brief thanks, then close/resolve.
  - e.g. `Thanks, looks good — <one clause naming what landed>. Resolving.`
- **Not addressed / partial:** reopen/keep open and ask what's blocking it — non-accusatory, no implication of fault, offer help.
  - e.g. `Reopening — I don't think <X> made it in yet. Could we <smallest concrete ask>? Happy to help if anything's in the way.`
- Do not offer "drop it" as an acceptable resolution unless the user explicitly allows dropping the behavior/coverage (SOP `2.0` Compatibility Gate).
  For the user's own work, dropping is not on the table by default.
- Resolution-state direction is independent of who last set it: an addressed-but-still-open item gets closed;
  a not-addressed-but-marked-resolved item gets reopened.

## Optional Niceties

- A light collaborative close (`Wdyt`, `lmk`) is the default nicety and covers most of what politeness needs here.
  It replaces longer warmth; do not add both. Drop it when it would not fit naturally (a pure factual answer, a resolve/close).
- Honest doubt is a nicety, not a weakness: naming the assumption you could not verify invites correction and reads as collaborative.
- Match the surface's register: terser for chat/Slack, slightly more structured for long-form email or a PR description when the content genuinely needs it.
