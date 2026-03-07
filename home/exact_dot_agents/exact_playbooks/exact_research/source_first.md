# Source-first Research (Clone + Grep)

Use this playbook when you are asked to "search the internet" or "figure out how
X works" and X has a publicly cloneable codebase (or source is otherwise
available).

Goal: minimize network requests by preferring local source inspection.

Do not use:

- for the current repo/worktree you are already in
- when the authoritative answer is product/account/runtime state rather than
  public source
- when the question is primarily news/release timing and source inspection would
  not answer it

First actions:

1. Identify the canonical upstream repo.
2. Resolve the exact ref that answers the user's question before reading code.
3. Clone or refresh `/tmp/agent-src/<owner>/<repo>`, then inspect locally.

## Procedure

### 1) Identify the canonical repo (one small query)

Prefer GitHub CLI:

- `gh search repos "<project name>" --limit 5`
- If you already have an owner/repo, skip search.

### 2) Clone into `/tmp` (and reuse it)

Pick a stable location:

- `/tmp/agent-src/<owner>/<repo>`

If it exists: reuse it and update it.

### 3) Resolve the target ref before inspecting

- First prove what ref answers the user's question:
  - current/latest behavior: use the upstream default branch
  - version/tag/release question: use that exact tag or release branch
  - branch- or commit-specific question: use that exact branch or commit
- If the user did not specify a ref and the answer depends on a non-default
  target, ask one direct question instead of assuming.

If the target is the default branch:

- `git fetch --prune --tags`
- `git checkout <default-branch>`
- `git pull --ff-only`

If you don't know the default branch:

- `git remote show origin | rg -n "HEAD branch"`

If the target is a specific tag/branch/commit:

- `git fetch --prune --tags`
- `git checkout <target-ref>`

### 4) Search locally

Prefer fast, mechanical tools:

- `rg -n "<symbol|keyword>" .`
- `rg -n "functionName\\(" .`
- `rg -n "type .*<Name>|interface <Name>|class <Name>" .`

Use `git log -S` to find semantic changes:

- `git log -S "<string>" --oneline --decorate -- .`

### 5) Only then use the web

Use web fetches for:

- docs that aren't in repo (`/docs`, wiki, website)
- issues/PR discussions
- release notes or changelogs not vendored in the repo

## Reuse rule

Keep the `/tmp/agent-src/...` clone around for reuse unless cleanup is
explicitly requested. Always `git fetch` / `git pull` before relying on it.

Output:

- Report the repo and ref you actually inspected.
- Say explicitly when you needed web sources after local source inspection and
  why source alone was insufficient.
