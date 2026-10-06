# Shared Review Rules

Every review mode uses these rules. Judging criteria live in `~/.agents/skills/k-review/references/judging_core.md`.
Before drafting public-ready comments, replies, descriptions, or a PR verdict, and before any posting step, load `~/.agents/skills/k-review/references/review_delivery.md`.
A local or plan report with no public-ready draft does not need it.

## Read-Only Probes

- Start read-only investigation immediately; do not ask before read-only `git`/`gh` checks.
- In large repositories, bound first-pass git probes: `GIT_OPTIONAL_LOCKS=0 git -c core.fsmonitor=false` for status, diff names, upstream, and log.
  If a plain git probe prints nothing after one short wait, stop it and rerun the bounded form.
- Keep searches narrow: path scopes, file globs, or exact symbols. Prefer the harness's native search tools for first-pass searches.
  Use shell `rg` only after narrowing; never run a bare repo-root `rg <pattern>` in a large repository.
- When saved or truncated output matters for a decision over every item, read the complete artifact.

## Hard Constraints

- Fix authority follows write scope from `~/.agents/skills/k-review/references/authorship.md`, not the review mode.
- Never create or switch worktrees proactively.
- Never infer commit, push, reply, resolve, or label authority from review ownership.
- Publication follows `~/AGENTS.md` §5: reuse approval only for its exact target, payload, and effect.
- Verified bot threads may use the authority of a flow the user invoked; human, mixed, or ambiguous threads stay supervised.

## Base-Branch Context Gate (Mandatory)

Goal: compare the change with how base (usually `main`) works today.

- The current branch or PR files and diff establish the changed behavior; base-ref reads are background evidence.
- Ask targeted questions of base source and history; do not run an unconditional query net.
- History encodes invariants and past bug fixes. Keep archaeology targeted and line-bounded:
  - Probe only non-obvious modified guards, conditionals, fallback branches, or legacy helpers.
  - Use `git blame -L <start>,<end> <base> -- <path>` or `git log -n 5 -L <start>,<end>:<path>`;
    `git log -n 5 -p -- <path>` only for the modified file.
  - Follow the identified commit to `gh pr view <pr>` or `gh issue view <issue>` for intent.
- A change that removes or weakens a guard added for a past defect or CVE is a HIGH regression finding.
- Report the base/head scope and evidence source in a `Base context:` line. This is assistant metadata, never GitHub comment text.

## PR Pending Reviews

For PR modes, run Pending Review Intake and Existing Pending Review Reconciliation from `~/.agents/skills/k-review/references/pr_common.md`.
If reconciliation is unknown and checkable, do not draft, post, or submit review feedback.
Every PR output that may become GitHub feedback includes the `Pending review reconciliation:` line.

## Review Queue

Long or multi-turn reviews keep a findings queue in a scratch file: `/tmp/k-review/<owner>-<repo>-pr<n>.md`, or `/tmp/k-review/local-<repo>-<branch>.md`.
Take `<n>` from this session's `,gh-prw --number` output, never from memory or a summary.

Record:

- identity: `pr: <owner/repo>#<n>` or `local: <base>..<head>`, `base_sha`, `head_sha`, `snapshot_at`, `discussion_at`
- per finding or thread: id, author type (`human`|`bot`), severity, `file:line`, one-line description, status (`open`|`fixed`|`dismissed`|`resolved`|`awaiting-approval`), and evidence
- checks run: command, result, head SHA
- open PR-body obligations and the current queue position

On a later turn, read the queue first and continue from it.
A fact the queue records with an anchor is trusted unless Drift reports its artifact changed.
When the user switches harness or session, save the queue summary with `,handoff save <topic>` (see `k-handoff`).
