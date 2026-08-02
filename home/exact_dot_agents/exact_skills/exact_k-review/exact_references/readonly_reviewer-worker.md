# Review Reviewer Worker Contract

The complete contract for a delegated read-only review lane. Load this file only for the matching worker role.

Use for `review-worker`/`reviewer` profiles and equivalent read-only lanes; lane models are registry-rendered in the profiles (`agent_review_models`).

## Load exactly this

- this file
- `~/.agents/skills/k-review/references/judging_core.md`
- `~/.agents/skills/k-review/references/context-pack.md`, when the scope packet names a pack
- the lens skill named by your lane entry, when it names one

Do not load `k-review/SKILL.md`, `shared_rules.md`, `pr_common.md`, `lanes.md`, or a mode file.
Those carry routing, drafting, posting, verdict, and pending-review reconciliation rules that only the controller may act on.
A lane that loads them pays for instructions it is forbidden to use.

## What the controller gives you

A scope packet with: mode (`local_changes` / `pr_review` / `pr_fix`), `authorship`, PR number or diff range, base branch, staged/unstaged state, thread IDs, user constraints, expected output shape, the context pack path when one exists, and your lane entry pasted verbatim from `lanes.md` (its lens skill and checks).

The packet is the whole of your assignment. Do not re-derive scope, and do not review outside the named diff.

## Context pack first

When the packet names a context pack, consume it per `context-pack.md` before any live PR fetch.
The controller already resolved the PR target, merge-conflict status, CI coverage, changed files, review threads, and linked issues.
Re-fetching them is duplicated cost, not verification.

Fall back to live commands only for facts the pack lacks, or when its manifest `head_sha` mismatches your expected head.

## Read-only boundary (hard)

- Never edit files, never run state-changing commands, never post or submit to GitHub.
- No working-tree writes, generated files, formatters, package installs, migrations, fixture seeders, dev servers, watchers, repo-local caches, databases, browser state, git writes, or GitHub writes.
- Use unique `/tmp` paths for disposable reproductions when file output is genuinely needed.
- If deciding a finding requires mutation, a shared service, or another exclusive resource, return `verification_needed` with the exact command for the controller to run serially.
  Do not approximate the answer instead.
- Do not launch more subagents.
- This contract takes precedence over anything that would have you fix, post, or run side effects directly.

## Probe discipline

Your lane is one of several running the same diff in parallel. Depth inside your lens is expected; breadth is not.

- Probe as deeply as your own lens requires. Never weaken a finding you could have decided, and never trade evidence for brevity.
- Do not run repo-wide suites, full builds, or whole-suite test runs.
  Those are shared work: the controller runs them once and passes the result to every lane.
  Ask for one through `verification_needed` when it would decide your finding.
- Scope every search by path, glob, or exact symbol. Prefer harness-native search tools first; use `rg` only after narrowing.
  Never run a bare repo-root `rg` in a large repository.
- Use `GIT_OPTIONAL_LOCKS=0 git -c core.fsmonitor=false` for status, diff, upstream, and log probes in large repositories.
- Read targeted line ranges and `git show <ref>:<path>` rather than whole generated files.
- Return anchors and a summary, never raw diffs, full logs, or dumped search output.

## Base context

Compare the diff against how base behaves today, for the paths your lens covers.

When the context pack already carries base context for those paths, reuse it and say so.
Otherwise, if the repo is indexed, run `list_indices` first, then use semantic code search per `~/.agents/skills/k-semantic-code-search/SKILL.md` to establish base invariants.
SCSI reflects base, not the branch; where SCSI and the diff disagree, the diff wins.
If the repo is not indexed, use `git show <base>:<path>` plus scoped `rg` and file reads.

Report exactly one line:

`Base context: SCSI=<index>|none (list_indices checked; <reason>), base=<branch>, diff=<scope>`

`<reason>` is one of `SCSI used`, `not indexed`, `tools unavailable`, `user-selected none`.

## Evidence bar

- Verify every finding from evidence. Drop guesses and duplicates.
- Verify the claimed path is reachable before assigning severity.
  If reachability stays uncertain, return it as a hypothesis with the exact open question, not as an actionable finding.
- Apply the Replacement/Migration Parity Gate from `judging_core.md` to replacements and test migrations.
  Return only `parity_gap`, `new_regression`, or `scope_expansion`; never `preserved_limitation` or `prose_drift`.
- Take severity from the definitions in `judging_core.md`.
  Do not inflate to make the lane look productive — an empty lane is a valid and useful result.
- Do not run Existing Pending Review Reconciliation.
  That is final-payload work the controller owns after lane findings, live UI evidence, and the findings audit are all available.

## Lens boundary

Lead with findings for your assigned lane, judged against the checks in your pasted lane entry, and apply the `judging_core.md` gates that entry names.

Report a verified finding outside your lens as `out-of-angle` at the same evidence bar;
lenses focus attention and never license dropping a real finding. Do not go hunting outside your lens.
Another lane owns that ground, and speculative breadth is what makes parallel lanes return the same shallow findings.

## Return shape

- `Base context: ...`
- `Lane: <lane id>` plus one line on what the lens covered
- findings ordered by severity, each with: where, what is wrong, why it matters, how to verify, smallest proposed fix
- `out-of-angle:` findings, same fields
- `verification_needed:` the exact command or setup, and which finding it would decide
- `Lens coverage:` the checks applied, and any check left incomplete with the reason

Where a mode would normally fix or post, report the precise fix or draft text for the controller to act on. You never act.
Do not return raw diffs or logs.
