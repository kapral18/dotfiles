---
name: k-long-jobs
description: "Use when a command can take minutes or outlast the tool timeout: time limits, background jobs, waiting in the same turn."
---

# Long jobs

`~/AGENTS.md` §3 points here for any command that can take minutes.

- Run a command that can take minutes under a time limit the task allows, such as `timeout 300`, and raise the tool's own timeout to match.
- A job that can outlast the tool's maximum timeout runs in the background under `timeout <limit>`, with the tool's background timeout set above that limit.
- If your answer needs its result, wait for it in the same turn: OMP `wait`; Claude Code, a foreground command that blocks until the job's output shows it ended, under the tool's maximum timeout, repeated while it runs.
- Past the limit, find the cause and report it; an optional verification probe that hits its limit settles nothing, so pick cheaper evidence (`~/AGENTS.md` §3 step 4).
