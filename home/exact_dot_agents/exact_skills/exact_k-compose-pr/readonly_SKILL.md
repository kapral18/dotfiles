---
name: k-compose-pr
description: "Use when drafting PR title/body or publication packet; no gh side effects."
---

# Compose PR Body

Use when:

- the user wants a PR title/body draft or PR publication packet only (no `gh` side effects)
- `~/.agents/skills/k-github/SKILL.md` needs a draft before creating/editing a PR

Scope:

- produce a PR title/body draft and PR publication packet only
- do not change PR metadata; use `~/.agents/skills/k-github/SKILL.md` for side effects
- read-only `gh`/GitHub API use is allowed only to resolve and fully read references needed for the draft

Do not use:

- creating/editing PRs in GitHub: `~/.agents/skills/k-github/SKILL.md`
- PR review feedback: `~/.agents/skills/k-review/SKILL.md`

Repo/org-specific overlays:

- A domain overlay is a repo/org-specific skill selected from the verified target repo/org, not guessed from wording.
- For `elastic` org / `elastic/kibana`, load `~/.agents/skills/k-elastic-domain/SKILL.md`.
- The overlay decides footer, release-note, label, ownership, and environment additions. This skill stays generic.

First actions:

1. Inspect current diff/branch context and user-supplied issue/PR refs.
2. For any PR, issue, comment, thread, asset, URL, or media reference the draft depends on, run GitHub Context Intake + Reference Resolution from `~/.agents/skills/k-review/references/pr_common.md`.
   Complete that gate per `pr_common.md` before summarizing.
3. If the body needs contested, historical, product, or team-precedent context not settled by direct refs, run Ambient Topic Exploration from `~/.agents/skills/k-review/references/pr_context_audits.md`.
4. Extract only verified evidence: summary, Test Plan, migration notes.
   Treat changed paths as scope clues only; do not turn them into PR body or Test Plan content unless they are part of a reviewer-runnable command or repro step.
   Verify each proposed Test Plan command or manual step from local source, CLI help, linked issue steps, or a safe probe before including it.
5. If issue linkage or test evidence is missing after intake, keep placeholders instead of inventing details.
6. If the repo is in `elastic`, load `~/.agents/skills/k-elastic-domain/SKILL.md` and apply its GitHub/PR composition section.
7. Load `~/.agents/skills/k-compose-pr/references/publication-packet.md`, then build the PR publication packet.
   Do not hand off while any required field is missing or `blocked`.
8. Keep title/body sources, linked issue intake, and unresolved placeholders with the draft and publication packet for `k-github`.

Rules:

- Follow `k-compose-pr/references/publication-packet.md` body rules for reviewability, Test Plan evidence, templates, sanitization, screenshots/uploads, and issue links.
- Keep composer-only unresolved placeholders outside the PR body and in the publication packet.

Output:

- Return the PR title/body draft and PR publication packet, ready for `~/.agents/skills/k-github/SKILL.md`.
- If important inputs are missing, name the placeholders needing confirmation.
- Always include the PR publication packet. A packet with a `blocked` required field cannot be handed to `k-github` for publication.
- When handing off, include the packet outside the PR body so `k-github` can build its publication preflight.
