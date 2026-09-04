# Route scope

1. **Route and scope.** Build a scope packet with:
   - mode: `local_changes.md`, `pr_review.md`, or `pr_fix.md`
   - `authorship`: `self`, `other`, or `unknown`
   - PR number or diff range
   - base branch
   - staged/unstaged state
   - thread IDs
   - user constraints
   - expected output shape
   - intent dependencies needed for judgment, or `none`
   - context pack path, or `none` for a non-PR/local mode where a pack could not be built
   - context pack manifest `head_sha`, or the exact blocker that prevented manifest generation
   - lane/verifier models: the review-model resolver values rendered into the deployed profiles;
     worker selection lines emit `model_required=<resolved value|inherit|default>` and the launch-confirmed `model_used`

   Resolve `authorship` via the review router's Role Detection. Do not duplicate worker review analysis in the controller.

Resolve `fix_authorized` (the working-tree-edit permission for this run) once here, alongside `authorship`.
It is `yes` when any of these hold:

- `authorship: self` (your own PR, or a local-changes flow);
- you are the PR assignee (verify via `gh pr view --json assignees`);
- the user explicitly states takeover/adoption intent for the PR
  - examples: "I'm taking this over", "my PR now", "fix what's missing", "take over this branch", or equivalent

When `fix_authorized: yes`, the fix step does NOT require a separate "fix" keyword —
an adopted/assigned/own PR is fix-authorized by virtue of ownership, not phrasing.
Explicitly invoking this skill on an own/adopted/assigned PR is itself the fix request, so the SOP §1 assess-vs-act gate is satisfied by the invocation.
When none of the above hold (`authorship: other`/`unknown` and no assignee/takeover signal), `fix_authorized: no`:
draft-only, never edit code. Record `fix_authorized` in the scope packet; the Act step branches on it.
`fix_authorized` governs only working-tree edits and verification mutations.
It never authorizes commit/push/post/resolve, which keep their own explicit-approval gates (git/github skills + Human-Visible Publication Gate).

Run the base-context preflight before fan-out.
The Base-Branch Context Gate in `~/.agents/skills/k-review/references/shared_rules.md` is blocking and controller-owned.
Read-only reviewer workers run with MCP/SCSI disabled and structurally cannot run it.
You MUST invoke `list_indices` yourself, trying both `scsi-main` and `scsi-local`.
Select the repo-matching index or prove none exists, and only then emit the `Base context:` line.
The line must use the real `<reason>`: `SCSI used` / `not indexed` / `tools unavailable` / `user-selected none`.
Never assert a `Base context: SCSI=none` line that you did not earn by running `list_indices`.
If your own runtime also blocks `list_indices`, say so explicitly as `tools unavailable` rather than implying the gate ran.
Keep the base-context preflight to base context only: run `semantic_code_search`, symbol analysis, code-chunk reads, broad code investigation, and finding construction only after reviewer workers launch.

Run durable-memory recall before fan-out with task-shaped queries, not the raw user prompt. At minimum run:

```bash
,ai-kb search "deep-review <mode> pitfalls gotchas" --limit 5 --json
,ai-kb search "<target repo/domain> review live-ui evidence gotchas" --limit 5 --json
```

Fold relevant capsule lessons into the scope packet as constraints, and cite capsule ids in the controller's plan.
This preflight is mandatory because slash-command prompts often contain too little semantic content for per-turn recall to surface the right capsules.

Materialize the read-only context pack before reviewer fan-out.
The pack roots, `manifest.json` fields, and the full artifact inventory (PR metadata/discussion/checks JSON snapshots, `body.md`, `diff.patch`, `files/<path>` head content, `base/<path>` base content) are owned by `~/.agents/skills/k-review/references/context-pack.md`; load it and produce every artifact it names that exists for the mode.
For PR modes, load `~/.agents/skills/k-review/references/pr_snapshot.md` here as well:
it owns the fetch commands, the `base_sha...head_sha` scope, media and reference capture, and the head + discussion Drift check that runs before lane launch and again before judgment.

All JSON collections must be complete and paginated, not previews. Scope packets MUST include the pack path and manifest `head_sha`.
Workers consult the pack first and fall back to live commands only for facts the pack lacks or when the manifest `head_sha` mismatches their expected head.
The measured reason for this controller cache is concrete: one real review had 42 changed files fetched 87 times via `git show` and `gh pr view` re-fetched 14 times across stateless lanes.
