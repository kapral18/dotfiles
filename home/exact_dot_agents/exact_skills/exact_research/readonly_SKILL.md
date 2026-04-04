---
name: research
description: Clone and inspect the source of a public GitHub repository to answer questions about it. Use when the user asks how a third-party project, library, or tool works, or gives a GitHub repo/file/directory URL to investigate.
---

# Source-first Research (GitHub/ref resolution + local source inspection)

Use this skill when you are asked to investigate an external/public project, library, or tool and the authoritative answer likely lives in its source repo. This includes explicit repo-inspection requests when the user gives repo URLs or asks you to inspect files/directories in that external repo.

Goal: answer external-codebase questions by resolving the right upstream/ref and then inspecting source locally.

Do not use:

- for the current repo/worktree you are already in
- when the authoritative answer is product/account/runtime state rather than public source
- when the question is primarily news/release timing and source inspection would not answer it

First actions:

1. Identify or confirm the canonical upstream repo.
2. Resolve the exact ref that answers the user's question before reading code.
3. Clone or refresh `/tmp/agent-src/<owner>/<repo>`, then inspect locally at that ref.

## Procedure

### 1) Resolve repo + ref with a small GitHub-first check

If the user already provided repo/file/directory URLs:

- extract owner/repo, ref, and path from those URLs
- use the repo page/search only as needed to confirm the canonical repo or default branch

If they did not provide a repo yet, identify it first. Prefer GitHub CLI:

- `gh search repos "<project name>" --limit 5`
- If you already have an owner/repo, skip search.

Do not start with raw content URLs or GitHub contents/tree APIs before you have resolved the repo/ref you intend to inspect.

### 2) Clone into `/tmp` (and reuse it)

Pick a stable location:

- `/tmp/agent-src/<owner>/<repo>`

If it exists: reuse it and update it.

### 3) Resolve the target ref before inspecting

- First prove what ref answers the user's question:
  - current/latest behavior: use the upstream default branch
  - version/tag/release question: use that exact tag or release branch
  - branch- or commit-specific question: use that exact branch or commit
- If the user did not specify a ref and the answer depends on a non-default target, ask one direct question instead of assuming.

If the target is the default branch:

- `git fetch --prune --tags`
- `git checkout <default-branch>`
- `git merge --ff-only origin/<default-branch>`

If you don't know the default branch:

- `git remote show origin | rg -n "HEAD branch"`

If the target is a specific tag/branch/commit:

- `git fetch --prune --tags`
- `git checkout <target-ref>`

### 4) Search locally

If the user pointed at specific files/directories, start there inside the local checkout, then expand outward as needed.

Prefer fast, mechanical tools:

- `rg -n "<symbol|keyword>" .`
- `rg -n "functionName\\(" .`
- `rg -n "type .*<Name>|interface <Name>|class <Name>" .`

Use `git log -S` to find semantic changes:

- `git log -S "<string>" --oneline --decorate -- .`

### 5) Use the web only after local source inspection when needed

Use web fetches for:

- docs that aren't in repo (`/docs`, wiki, website)
- issues/PR discussions
- release notes or changelogs not vendored in the repo

## Reuse rule

Keep the `/tmp/agent-src/...` clone around for reuse unless cleanup is explicitly requested. Always run `git fetch --prune --tags` before relying on it. Do not run `git pull` unless the user explicitly asks to update a local tracking branch.

Output:

- Report the repo and ref you actually inspected.
- If the user gave repo URLs, say how they mapped to the inspected repo/ref.
- Say explicitly when you needed web sources after local source inspection and why source alone was insufficient.
