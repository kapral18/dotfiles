---
sidebar_position: 2
title: "Run Ralph detached"
---

# Run Ralph: detached autonomous work

You want work done **off your desk** — it survives closing the session, you watch it like CI. Ralph runs a planner → executor → reviewer → re-reviewer loop where acceptance checks are _executed by the orchestrator_, so an LLM saying "pass" cannot outvote a failing check.

**Prerequisites:** any terminal inside tmux. Check health once with `,ralph doctor`.

## The one-liner form

```bash
,ralph go --goal "Add a count command to todo.py: prints the number of open todos; cover it in test_todo.py"
```

That's it. Your prompt returns immediately (the runner detaches). Ralph's planner writes the contract from your sentence — including runnable checks — then the loop drives itself.

Write the goal like a commit subject plus constraints: name the file, the behavior, and where tests go. Vague goals make the planner ask you questions before starting (the run parks until you answer — see below).

## The spec-file form (you author the contract)

If you already ran the [spec flow](spec-and-build.md), the packet ends with a JSON block. Save it and:

```bash
,ralph go --spec /tmp/e2e-todo/todo-spec.json --workspace /path/to/repo
```

The planner is skipped entirely — your contract drives the run verbatim.

## Watching it

```bash
,ralph runs                 # list runs: id, status, goal
,ralph status <run-id>      # one line; exit 0 iff completed — scriptable
,ralph preview <run-id>     # rich summary
```

Or press **`prefix + A`** in tmux for the live dashboard (runs left, roles right, log tail below). Every role runs in a real tmux pane you can attach to: `,ralph attach <run-id> --role executor-1`.

What healthy progress looks like in the decisions log (`,ralph preview` shows it):

```text
iter 1: criteria checks 1/3 passed (failing: python3 -m unittest -q test_todo)
iter 1: re_reviewer adjudicated -> needs_iteration
iter 2: criteria checks 3/3 passed
iter 2: PASS, run complete
```

Iteration 1 failing is **normal** — the loop exists to converge. The machine-run check line is your ground truth; reviewers see the same results and can't wave a red check through.

## When Ralph asks you something

If a role needs a human decision the run parks as `awaiting_human`. Answer from the dashboard (press `A` on the run) or the CLI:

```bash
,ralph answer <run-id> --json - <<< '{"q1":"use src/parser.ts"}'
```

The run resumes itself after the last answer.

## When it finishes

`summary.md` in the run dir (shown by `,ralph preview`) has a checklist of every criterion and the machine-run check table. Terminal states:

| Status                            | Meaning                                                           | Do                                                   |
| --------------------------------- | ----------------------------------------------------------------- | ---------------------------------------------------- |
| `completed` / validation `passed` | every check green, cross-family reviewers agreed, artifact sealed | inspect the workspace diff, commit                   |
| `needs_human`                     | a role hit a wall; reason in `block_reason`                       | read it, fix or `,ralph replan <run-id>`             |
| `failed`                          | iteration/time cap without a pass                                 | `,ralph preview` to see which check never went green |

## Steering mid-run

```bash
,ralph replan <run-id>      # re-plan against progress so far (replaces an operator spec too)
,ralph kill <run-id>        # stop one run (panic button: kill --all)
,ralph rm <run-id>          # archive when done looking
```

## Pivots from here

- Result needs a careful look → run the [review flow](review-your-changes.md) over the produced diff.
- Run keeps failing the same check → the contract may be wrong, not the code: `,ralph replan`, or take it in-session with [spec + /build](spec-and-build.md) where you can watch each step.
