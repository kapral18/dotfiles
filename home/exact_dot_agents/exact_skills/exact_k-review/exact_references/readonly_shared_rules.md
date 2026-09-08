# Shared Review Rules

All review modes load this file. Do not duplicate these rules in mode files.

The surface-agnostic judging engine lives in two files under `~/.agents/skills/k-review/references/`:

- `judging_core.md` covers Truth Validation, selected counterexamples, the gates (State-Machine, Async-Derived State, Context-Divergence, Scale-Behavior, Deletion-Safety, Replacement/Migration Parity, Historical-Rationale, Semantic-Projection, Product-Flow, Signal-Quality, Systemic-Risk), and Severity.
- `judging_pipeline.md` covers integrated coverage, hygiene, and findings presentation within the single final Verify stage.

Load both alongside this file.

This file carries the shared intake, base-context, and persistence rules layered on top of that core.
Before drafting review comments/replies/descriptions or recommending a PR verdict, load `~/.agents/skills/k-review/references/review_delivery.md`.
Before any GitHub posting step, load that same reference and apply its Posting Boundary.
Do not load delivery mechanics for a local/plan report that contains no public-ready review draft.

## Read-Only Probes

- Start read-only investigation immediately. Do not ask for confirmation before read-only `git`/`gh` checks.
- In large repositories, make first-pass git probes bounded: use `GIT_OPTIONAL_LOCKS=0 git -c core.fsmonitor=false` for status, diff names, upstream, and log probes.
  If a plain git probe produces no output after one short wait, stop it and rerun the bounded form.
- Keep searches narrow by default: include path scopes, file globs, or exact symbols.
  When the harness provides native search/listing tools, prefer those for first-pass broad searches.
  Use shell `rg` only after narrowing by path, glob, or exact symbol; never run bare repo-root `rg <pattern>` in a large repository.
  Do not run broad repo-wide searches or dump full command output when a file list, count, or targeted lines answer the question.
- When command output is saved/truncated, recover only the exact lines needed for the current decision unless the decision depends on every item.

## Hard Constraints

- Review alone is read-only regardless of authorship.
  Fix requests authorize scoped production before final Verify, not automatic final repair.
- Final workers use existing evidence and return once; they do not repeat successful checks, mutate shared state, or invoke other models.
- Execute known final commands directly with complete retained logs and actual exit status; no mechanical runner agent is required.
- Keep git/worktree changes and human-visible effects within explicit user authority. Never create/switch worktrees proactively.
- Publication remains draft → show exact payload/target → explicit approval unless an applicable bounded packet authorizes it.
- Verified bot threads may use their explicitly invoked flow's authority; ambiguous/mixed or human threads remain supervised unless the user approved the bounded sequence.
- Never infer commit/push, reply/resolve, or label authority from review ownership.

## Base-Branch Context Gate (Mandatory)

Goal: compare the diff against how base (usually `main`) works today.

### Evidence selection

Reuse the packet's relevant base evidence.
Use scoped source/history for targeted questions and semantic search for substantial missing context when useful.
If using semantic search, resolve the index through `list_indices` before querying and verify which snapshot it represents.
Do not claim an index was checked when no tool ran. A missing index does not block usable local-source evidence.
Do not run an unconditional multi-index preflight or query net when the relevant evidence is already available.
Current branch/PR files and diff establish the changed behavior; index results are background evidence, not the reviewed candidate.

### Historical Archaeology & Provenance (History Dimension)

History encodes invariants, past bug fixes, edge cases, and architectural context invisible to static code search:

- In massive repositories, archaeology must be **targeted and line-bounded**, never run as whole-file blame or unconstrained recursive log traversals:
  - Probe only high-uncertainty or non-obvious modified guards, conditionals, fallback branches, or legacy helpers where origin intent is ambiguous.
  - Always bound line ranges and commit depth: `git blame -L <start>,<end> <base> -- <path>` or `git log -n 5 -L <start>,<end>:<path>`.
  - Use `git log -n 5 -p -- <path>` only when scoped to the immediate modified file.
  - Look up context from the identified commit via `gh pr view <pr>` or `gh issue view <issue>`.
- Check whether the diff inadvertently removes or weakens a guard previously added to fix a past defect or CVE.
- Classify changes that unknowingly resurrect historical bugs as HIGH regression findings.

### Base context reporting

Identify the actual base/head scope and evidence source in the compact review receipt.
State source/index unavailability precisely without inventing a completed preflight.
This is assistant metadata, not GitHub comment-body content.

## Draft Style (Public-Ready)

Before drafting or a PR verdict: load `review_delivery.md` (matching heading).

## Pending Review Semantics (Definition + Content Boundary)

Before drafting or a PR verdict: load `review_delivery.md` (matching heading).

## Existing Pending Review Awareness (Before Drafting or Posting)

For PR modes, run Pending Review Intake and Existing Pending Review Reconciliation from `pr_common.md`.

Keep this boundary here: if reconciliation is unknown and locally/API-verifiable, do not draft/post/submit review feedback.
Every PR-review output that may become GitHub review feedback must include the `Pending review reconciliation:` line from `pr_common.md`.

## Review Verdict (PR Review Mode Only)

Before drafting or a PR verdict: load `review_delivery.md` (matching heading).

## Review Persistence

The internal findings queue and review progress are ephemeral by default.

Survive conversation pruning by reusing the existing hook-managed memory system.

Do not invent a parallel store:

- Convention: `/tmp/specs/<pwd>/` from the parent SOP. Topic key: `review-<pr-number>` for PR modes (else `k-review`).
  Take `<pr-number>` from the `,gh-prw --number` output of this session, never from memory or a context summary;
  a summarized context has produced a wrong number before, and the wrong bucket then carries every later turn.
- The agent-owned intent file is `<topic>.txt`.
- The hook system additionally maintains `<topic>.worklog.jsonl`.
- Inspect review state only with a topic- or session-bound `,agent-memory status`;
  sessionless status can resolve a different topic in parallel sessions.
- If Agent Hook Context names the active topic, inspect that exact bucket with `,agent-memory status --topic <active-topic>`.
- If Topic Buckets supplies a session ID, bind the review bucket with `,agent-memory select <topic> --session-id <id> [--create]`, then inspect it with `,agent-memory status --session-id <id>`.
- On the first turn of a PR flow, check for the spec file and resume from it.
  After each thread/finding, append to `<topic>.txt` so the loop is resumable:
  - findings/threads: `comment_id`, author-type (`human`|`bot`), severity, file:line, one-line description, status (`open`|`fixed`|`dismissed`|`resolved`|`awaiting-approval`)
  - decision + evidence per thread (what base does, what changed, what was tested)
  - validation runs: commands + pass/fail + head SHA pushed
  - PR body obligations still open (sections to update, deletions to disclose)
  - open audit questions (e.g. unresolved `,kbn-pr-audit` findings)
  - current position in the queue (for iterative/Drain Mode) and base-context metadata
- Review identity (write on the first turn; update when drift changes it):
  - `pr: <owner/repo>#<n>` (or `local: <base>..<head>`), `pack: <root>`, `base_sha`, `head_sha`, `snapshot_at`, `discussion_at`
- Lane rows and the discipline governing them are root bookkeeping: see `## Root moves`.
- Verified-fact and media ledger:
  - `fact: <claim> — <anchor> — <verified_at>` for every fact this session verified
  - `media: <file> — <caption> — viewed` for every image viewed; view each image once
  - `stage: <Scope|Understand|Produce|Verify|Deliver>` with artifact and final receipt pointers
- After a context summary, a `fact:` or `media:` line this session wrote with an anchor is trusted.
  If Drift reports its artifact changed, mark the evidence stale; do not automatically restart verification.
  Re-reading the pack, re-viewing media, or re-running a gate to confirm a ledgered fact is a defect, not diligence.
  Worker reports remain provisional; the final stage consumes underlying evidence without a second certification loop.
- On subsequent turns, check for the spec file first and resume from it if present.

## Posting Boundary

Before any GitHub posting step: load `review_delivery.md` → "Posting Boundary".

## Root moves

Only the active root/main session follows this section; a delegated leaf skips it and returns findings to its parent.
Substantial base-context questions use a strong research packet; simple targeted reads remain inline.
Select queries from the actual uncertainty, not an unconditional multi-angle roster.
Keep raw evidence in the context pack and compact decisions/pointers in root context.
Record each packet ID, stage/category, owned question, model/effort, and active/terminal result in the existing topic.
Never relaunch an active/terminal packet, wake completed workers, or present a final verdict while required results are missing.
