# Reviewer roster

1. **Launch the reviewer lane roster.**
   - Select lanes from `~/.agents/skills/k-review/references/lanes.md`, which owns the lens catalog, each lens's trigger, and its checks.
     Use only lanes that file defines, listed there rather than re-listed here.
     Follow its selection procedure: scope-level evidence only (mode, changed paths, `git diff --stat`, `--diff-filter=D` status, context pack manifest); roster selection is not implementation analysis — select from scope-level evidence, leaving code bodies unread for it.
     - Always include `correctness-regressions`.
       For a single-surface diff with no independent risk trigger, that one sighted lane is enough.
       Launch it on the cross-family lane pick (`lanes_cross` profile where the harness registry fields one):
       generation recall bounds every later phase — refuters prune candidates but never expand them —
       so the primary finder carries family diversity, angle lanes carry breadth diversity, and final adversarial verification keeps its own cross-family pass after findings audit.
       When no cross-family lane is fieldable, report `finder_family=same (degraded)` and continue.
     - Launch one to three sighted lanes by default.
       Use four or five only when the user explicitly asks for maximum rigor or when multiple high-risk classes are present at once (security/auth, persisted data/migration, public API, state-machine behavior, deletion/replacement, or user-visible product flow).
     - Paste each selected lane's `Lens skill` line and `Checks` list verbatim into that worker's scope packet.
       Workers never load `lanes.md`; pasting the entry costs a few lines instead of the whole registry.
     - If more lenses are implicated than the budget allows, fold the extras into the closest launched lane as named secondary emphases and say which were folded.
     - State the roster and the scope-level evidence for each selected lane in the output.
   - Run any repo-wide suite, full build, or whole-suite test run **once here**, before the launch batch, and put the result in every scope packet.
     Lanes are instructed not to repeat shared work; if the controller skips it, no lane covers it.
   - Lane model selection is declarative, never steered at runtime: every repo-owned review profile's `model` frontmatter is rendered through `review-agent-model.partial` from the chezmoi model data (a concrete id, `inherit`, or omitted for the harness config default).
     The controller launches named profiles as-is and never passes lane model overrides;
     generic fresh-eyes launches pass the same resolved lane value as the profile-equivalent model because they cannot use a context-bearing reviewer profile.
     A wrong or stale model is fixed in the registry/bands, not the launch.
     The angles are this phase's breadth axis; family diversity sits at the primary finder (`lanes_cross` when fielded) and at final adversarial verification.
   - Emit all reviewer-lane launches, fresh-eyes included when it applies, in one message (a single tool-call batch).
   - Use the harness's native reviewer worker profiles or task mechanism (`k-agent-review-worker`/`k-agent-reviewer` profiles, or a generic task type carrying `reviewer-worker.md`); read `runtime-harnesses.md` for per-harness launch and model-inheritance caveats.
   - Hard-read-only caveat: for Cursor, follow `runtime-harnesses.md`.
     Cursor Task launches and Cursor profile shims for `/k-deep-review` must use `readonly: false`.
     If a worker reports Ask/read-only mode blocked shell/git/`gh`/Playwriter, discard that launch result and rerun with `readonly: false`.
   - Cursor Task background caveat: reviewer, PR-necessity, live-UI, and findings-audit workers should remain real Cursor background subagents.
     Use Cursor Task `run_in_background=true` for those launches when the active Cursor Task schema exposes it.
     Wait on Cursor subagent ids only through a Cursor-native subagent completion signal;
     shell `Await`/`AwaitShell` is for shells, not subagent ids.
     If no native completion signal is available, end the controller turn and wait for the completion notification, or do one transcript completion check; a single check replaces repeated sleep polling.
   - Give each worker the scope packet and one angle from the roster above.
   - If `runtime-harnesses.md` says the active harness cannot fan out from the current context, run them as that file directs and state why.
   - This phase is blocking as a phase.
     After the reviewer workers are launched, do not start adversarial verification, live UI verification, findings audit, or controller judgment until every launched lane's output is available, fresh-eyes included when it was launched.
   - Keep the parallel lanes concurrency-safe:
     - Prefer file reads, local source inspection, context-pack reads, `git show`/`git diff` reads, targeted line-bounded historical archaeology (`git blame -L`, `git log -n 5 -L`), isolated `/tmp` reproductions, and verification commands.
       The verification commands should improve finding validity or coverage.
   - Allow non-mutating verification at whatever depth is needed, including expensive static analysis or full suites.
     Outputs/caches must be read-only or isolated away from shared repo/runtime state.
   - Run dev servers, watchers, database migrations, package installs, code generators, formatters, fixture seeders, and cache/artifact-writing commands only from the controller, never from reviewer lanes.
   - If stronger verification requires shared-state mutation, a shared service, or an exclusive runtime resource, return `verification_needed` with the exact command/setup.
     Let the controller run it serially after aggregation or during the act phase.
   - Each candidate finding must include a reachability statement for the claimed path.
     If the claimed UI/API/state path may be unreachable, the worker must verify reachability before assigning severity or mark it as a hypothesis for the controller to verify/drop.
   - **Blind fresh-eyes clarity lane (conditional, same launch batch).**
     - Launch an additional read-only worker on `~/.agents/skills/k-review/references/fresh-eyes.md` only when the mode is `pr_review.md` or `local_changes.md`, the diff adds or changes human-maintained code or docs, and scope-level evidence shows comprehension risk: public interface/naming changes, AI-facing or user-facing prose, state-machine/replacement/deletion work, more than 500 changed lines, or more than 10 changed files.
     - Skip it for `pr_fix.md`, generated/vendored/lockfile-only diffs, and human-maintained diffs without one of those comprehension-risk signals; record the skip reason.
     - Blindness is this lane's diversity axis.
       Its packet is only the diff scope (base ref, changed paths, or an explicit diff command), withholding the PR number/title/body, commit messages, issue text, thread content, prior findings, and controller narrative.
     - Launch mechanics, allowed reads, and the worker selection line fields are owned by `fresh-eyes.md`;
       do not launch it through the named reviewer profiles, which preload the `k-review` skill and PR context.
     - This lane is part of the phase-3 barrier: live UI, findings audit, final adversarial verification, and judgment wait for it like any reviewer output.
