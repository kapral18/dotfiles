---
name: k-kibana-management-ownership
description: "Use when checking elastic/kibana ownership, reviewer targets, who owns a path, or kibana-management CODEOWNERS/Ownership Gate paths; propose-only."
---

# Kibana Management Ownership (Propose-Only)

Use when:

- composing or reviewing an `elastic/kibana` PR and reviewer/ownership guidance is needed
- checking whether changed paths fall under `@elastic/kibana-management` (the user's team) before a side effect, per SOP §3.1 Ownership Gate
- asked "who owns this path / who should review this?"

Do not use:

- outside `elastic/kibana` repos (other repos: ask once which team applies, remember for the session)
- to apply reviewers/labels or post anything — this skill is propose-only; side effects go through the `k-github` skill, wording through the `k-communication` skill

## Mechanics

`,codeowners` reads `.github/CODEOWNERS` in the current repo (run from the repo root or a worktree):

```bash
,codeowners management        # paths owned by teams matching "management" (case-insensitive substring)
,codeowners -p management     # paths only, for scripting/diffing
,codeowners --owner-of path   # last matching CODEOWNERS entry for one path
,codeowners                   # all owners with path counts
```

The team identity is `@elastic/kibana-management`.

## Procedure

1. Collect the changed paths (`git diff --name-only <base>...` or the PR's file list via `gh`).
2. Map each path to its owner with `,codeowners --owner-of <path>`.
   - Do not exact-match changed files against `,codeowners -p kibana-management`;
     that output is CODEOWNERS path patterns/roots, not an exhaustive file list.
     A descendant path can be in-team because its nearest matching CODEOWNERS root is in-team.
3. Classify:
   - All paths in-team -> proceed normally; no extra reviewers needed beyond team norms.
   - Any path out-of-team -> list those paths with their owning teams; propose the owning teams as reviewers and flag that the side effect needs explicit approval (SOP §3.1).
   - Unowned paths -> say so explicitly; do not guess an owner.
4. Present the proposal (paths -> owners -> suggested reviewers). Stop there; apply nothing.

## CODEOWNERS gotchas (verified)

- Matching is last-match-wins: a later, more specific entry overrides an earlier one.
- Owner-less entries are valid and CLEAR ownership for matching paths — a path matched last by an owner-less entry is unowned, not owned by the previous match.
- CODEOWNERS missing or `,codeowners` unavailable -> skip ownership classification and say so; do not infer ownership from directory names.
