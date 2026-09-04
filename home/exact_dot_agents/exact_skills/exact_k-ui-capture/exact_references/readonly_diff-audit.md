# Diff audit

## Step 1 — Audit the diff for capturable UI changes

Inspect the change set and itemize what can be visually proven:

1. Resolve the diff: `git diff origin/<base>...HEAD` plus staged/unstaged working-tree changes, or `gh pr diff <n>` when a PR is named.
2. Load `~/.agents/skills/k-ui-capture/references/proof-mode.md` and build its Behavior inventory:
   apply the split test (one item per independently observable difference), the classification test (static state → screenshot pair;
   interactive sequence, timing, or continuous behavior → video pair), the coverage plan (dedicated pair per item by default;
   one shared pair when same-trigger items are each plainly visible in it), and the baseline test (`baseline` vs `intra-change` vs head-only) to every user-visible change.
   Mechanical, test-only, or non-rendered changes are not capture items.
3. When the diff has no user-visible surface, report `Not applicable` with the changed-file evidence and stop.

Completion criterion: every changed file is accounted for as part of an inventory item or explicitly excluded, every item carries its media classification, or a `Not applicable` verdict with evidence ends the run.

## Step 2 — Assemble the capture inputs

Build the exact inputs the proof-mode contract's Caller supplies section requires, per item:

- the built/changed worktree path and branch/sha, and the changed UI paths from Step 1
- the intended visual/UI state or behavior (the oracle), derived from the diff, linked issue/PR context, or the user's description;
  ask the user once when an item's oracle stays ambiguous after that
- the selected target packet and required runtime config, resolved as the proof-mode contract's Caller supplies section directs
- a distinct `/tmp/ui-capture-<item-slug>/` output folder per item, or per shared pair when the coverage plan consolidates items

Completion criterion: every item has a testable oracle and a complete input set, or the item is reported blocked with what is missing.
