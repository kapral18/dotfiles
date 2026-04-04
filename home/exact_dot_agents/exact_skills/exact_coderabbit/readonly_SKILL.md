---
name: coderabbit
description: Review-fix loop on local changes using CodeRabbit before opening a PR. Use only when coderabbit is explicitly mentioned and the current repo is under the elastic GitHub org.
tool_version: coderabbit 0.3.9
---

# CodeRabbit Review-Fix Loop

Use when:

- coderabbit is explicitly mentioned AND the current repo is an `elastic/*` repo

Do not use:

- human-style PR review: `~/.agents/skills/review/SKILL.md`
- GitHub side effects: `~/.agents/skills/github/SKILL.md`

First actions:

1. Verify the current repo is under the `elastic` GitHub org (`git remote get-url origin` must contain `elastic/`). Abort if not.
2. `command -v coderabbit` — abort with install instructions if missing.
3. `coderabbit auth status` — abort with `coderabbit auth login` if not authenticated.
4. Confirm staged changes do not contain secrets or credentials.

## Phase 1: Build context

Before running coderabbit, gather base-branch context so you can judge its findings against how the codebase actually works.

1. Read the local diff (`git diff` / `git diff --cached`) to understand what changed.
2. From the diff, generate semantic questions about the contracts, invariants, and patterns the changed code touches (e.g. "how is X validated elsewhere?", "what calls this function?", "what pattern does the codebase use for Y?").
3. Load `~/.agents/skills/semantic-code-search/SKILL.md` and follow its preflight (`list_indices` on both `scsi-main` and `scsi-local`). If the repo is indexed, query each question via `semantic_code_search` / `symbol_analysis`. If not indexed, fall back to local `rg` / file reads.
4. Carry the answers as working context into Phase 2.

## Phase 2: Review-fix loop

1. Run `coderabbit review --prompt-only` (may take minutes on large diffs — let it finish).
2. Read the output. For each finding, use the context from Phase 1 to judge whether the finding is valid — does it align with how the codebase actually works, or is coderabbit missing context?
3. For findings you judge valid: implement the fix. For findings you judge incorrect or not worth it: skip them.
4. Re-run `coderabbit review --prompt-only` to check whether your changes introduced new findings.
5. Repeat until no actionable findings remain.
6. Cap at three iterations. If findings persist after three rounds, report what remains and stop.

## Commands

```bash
coderabbit review --prompt-only                        # all local changes
coderabbit review --prompt-only -t uncommitted         # only unstaged/staged
coderabbit review --prompt-only -t committed           # only committed, not pushed
coderabbit review --prompt-only --base develop         # diff against a branch
coderabbit review --prompt-only --base-commit abc123   # diff against a commit
coderabbit review --prompt-only -c .coderabbit.yaml    # pass project review instructions
```

## Notes

- Must run inside a git repo.
- Default scope is all local changes (`-t all`).
- `--config` / `-c` accepts instruction files to tune the review.
- Free tier: 3 reviews/hour — budget iterations accordingly.
