---
name: kbn-resolve-backport
description: Resolve Kibana backport cherry-pick conflicts, validate the adapted changes, stage the resolved files, and stop. Manual-only skill for requests that explicitly ask to use the kbn backport conflict resolution workflow.
disable-model-invocation: true
---

# Kibana Backport Conflict Resolution

Use this skill only when explicitly invoked by name, or when the user asks for the same manual backport conflict resolution procedure.

## Contract

- Resolve conflicts in the target Kibana backport checkout, usually `~/.backport/repositories/elastic/kibana`.
- Verify the resolution in context, adapting paths and implementation style to the destination branch.
- Stage only the resolved files and stop. Do not commit, push, continue the cherry-pick, or open a PR unless the user explicitly asks.
- Preserve destination-branch behavior unless the incoming PR intentionally changes it.
- Compatibility impact default: `none`. Do not add compatibility shims unless explicitly requested.

## First Steps

1. Follow the local `git` skill for git safety.
2. Identify the exact checkout and branch:
   - `git status --short --branch`
   - `git diff --name-only --diff-filter=U`
   - `git show --stat --oneline CHERRY_PICK_HEAD` when present
   - `git log -1 --oneline`
3. Inspect conflict context before editing:
   - `git diff --cc -- <conflicted-path>`
   - `git show CHERRY_PICK_HEAD -- <changed-paths>`
   - read the conflicted files and nearby destination-branch code
4. Check ownership before staging in `elastic/kibana`:
   - `,codeowners -p @elastic/kibana-management`
   - If any affected path is outside team ownership, stop and ask before the side effect.

## Resolution Rules

- Treat the destination branch as source of truth for paths, generated-vs-source files, test conventions, parser/runtime shape, and available tooling.
- If the incoming commit touches a file that does not exist or is superseded on the backport branch, find the branch-equivalent file before applying the change.
- For deleted-by-us conflicts, verify whether the destination branch intentionally removed or relocated the file. Prefer applying the behavior to the active branch file, then remove the stale incoming path.
- For additive test conflicts, keep both destination-branch coverage and incoming PR coverage when they test distinct behavior.
- Do not remove unrelated destination-branch behavior while cleaning conflict markers.
- Search for conflict markers after every edit:
  - `rg '<<<<<<<|=======|>>>>>>>|\|\|\|\|\|\|\|' <resolved-files>`

## Validation

Run the smallest checks that prove the adapted backport is correct:

- Focused Jest for changed tests, using the closest package config:
  - `node scripts/jest --config=<package>/jest.config.js <test-file>`
- ESLint on changed source and test files:
  - `node scripts/eslint <changed-files>`
- Scoped type check for the owning package:
  - `node scripts/type_check --project <package>/tsconfig.json`
- Kibana change check when available:
  - `node scripts/check_changes.ts`

If validation fails because dependencies are not linked after switching branches, run `yarn kbn bootstrap`, then rerun the failed checks.

If `scripts/check_changes.ts` or a branch-local validation script is missing, report that it was unavailable and use the focused checks above.

## Staging And Stop

After validation passes:

1. Review final diffs:
   - `git diff -- <changed-files>`
   - `git diff --cached -- <changed-files>`
2. Stage only the resolved backport files:
   - `git add <resolved-files>`
3. Confirm:
   - `git diff --check --cached`
   - `git diff --name-only --diff-filter=U`
   - `git status --short --branch`
4. Stop and summarize:
   - branch and PR/commit being backported
   - files staged
   - validation commands and results
   - unresolved conflicts, if any
   - `Compatibility impact: none | removed (requested) | kept existing (requested)`
