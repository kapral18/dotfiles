# Source-first Research (Clone + Grep)

Use this playbook when you are asked to "search the internet" or "figure out how
X works" and X has a publicly cloneable codebase (or source is otherwise
available).

Goal: minimize network requests by preferring local source inspection.

## Procedure

### 1) Identify the canonical repo (one small query)

Prefer GitHub CLI:

- `gh search repos "<project name>" --limit 5`
- If you already have an owner/repo, skip search.

### 2) Clone into `/tmp` (and reuse it)

Pick a stable location:

- `/tmp/agent-src/<owner>/<repo>`

If it exists: reuse it and update it.

### 3) Pull latest before inspecting

Run:

- `git fetch --prune --tags`
- `git checkout <default-branch>`
- `git pull --ff-only`

If you don't know the default branch:

- `git remote show origin | rg -n "HEAD branch"`

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

