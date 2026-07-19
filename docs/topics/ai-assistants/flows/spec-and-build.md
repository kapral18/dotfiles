---
sidebar_position: 1
title: "Spec a feature, build it hands-free"
---

# Spec a feature, then build it hands-free

You have an idea ("add a `done` command to my CLI") and want the agent to implement it without babysitting, but with proof it worked. Two steps: `k-spec` turns the idea into a contract; `/k-build` implements it in-session, or `,palantir summon --criteria` runs it detached. You touch exactly two gates.

**Prerequisites:** a Claude Code (or Cursor/Copilot) session in your repo. Nothing else.

## Step 1 — ask for a spec

Type, in your own words:

```text
develop a spec for: a `done <id>` command that marks a todo completed and hides it from list
```

The `k-spec` skill fires on "develop a spec". The agent will now:

1. Check the work isn't already done (git log, issues, memory).
2. Ask you fork-closing questions — **one at a time, always with a recommended answer**, like:

   > Should `done` renumber the remaining ids, or keep them stable? Recommended: stable — renumbering would break `done <id>` against a printed list.

   Answering `yes` or `stable` is enough. If a question is empirical ("which layout feels right?"), expect the agent to build a tiny throwaway prototype and show you instead of asking you to imagine.

3. Write acceptance checks and **run each one now, expecting failure** (the feature doesn't exist yet — a check that already passes proves nothing). You'll see pasted runs like:

   ```text
   check: DB=$(mktemp); TODO_DB="$DB" python3 todo.py done 1 ...
   now: red (exit 2, 2026-07-02 — argparse rejects 'done')
   ```

## Step 2 — gate 1: approve the packet

The agent shows the full spec packet: goal, in/out of scope, criteria with red-proven checks, compatibility intent. This is your steering wheel — **read it like a contract**, because everything after runs unattended against it.

- Wrong scope or missing criterion? Say so in plain words ("also cover the empty-list case") — the packet is revised and re-shown.
- Good? Say `approved, /k-build it`.

## Step 3 — hands-free build

Type:

```text
/k-build
```

Then do something else. The agent plans, implements, runs each check as it goes, runs the repo's lint/tests, sends an adversarial verifier subagent to try to _disprove_ every criterion, and cleans up its own diff. It will **not** ask you anything unless it hits a genuine blocker or discovers the packet's premise was wrong (then it stops and returns to gate 1 — by design).

## Step 4 — gate 2: read the report

The final message is a ledger, one row per criterion:

```text
1. done hides the completed item — green (check exit 0) — verdict: confirmed
2. tests cover done            — green — verdict: confirmed
...
Completion gate: clear
Compatibility impact: none
```

`confirmed` means the adversarial verifier failed to break it. A `refuted` row never reaches you silently — it goes back to implementation first. If a criterion was visual, the build ran `k-ui-proof` against the running app and its row is backed by a screenshot saved in its own distinct `/tmp/<folder-name>/` folder — proof the intended visual was actually built. Nothing is committed yet: say `commit it` / `draft the PR` (which uploads those screenshots itself and embeds them as `user-attachments` URLs) when satisfied.

## When things go sideways

| You see                         | It means                                   | Do                                                                             |
| ------------------------------- | ------------------------------------------ | ------------------------------------------------------------------------------ |
| Agent asks a question mid-build | genuine blocker or premise correction      | answer it; the packet may be re-gated                                          |
| A ledger row says `blocked`     | check couldn't run; exact command included | run the shown command yourself or fix the env                                  |
| You changed your mind mid-build | —                                          | just say it; the flow stops and re-gates rather than finishing the wrong thing |

## Pivots from here

- Want it running detached instead of in this session → say `hand it to Palantír instead` at gate 1, then pass the packet criteria JSON to `,palantir summon --criteria` ([architecture](../palantir.md)).
- High-stakes change → say `plan-review the packet first` before approving; a reviewer tries to break the _contract_ before any code exists.
- Just want the idea filed, not built → `draft an issue from this packet`.
