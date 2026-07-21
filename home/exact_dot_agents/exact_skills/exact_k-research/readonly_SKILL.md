---
name: k-research
description: "Use when inspecting an external public repository from source or synthesizing factual claims across multiple public sources."
---

# Research

Choose the smallest branch that answers the question:

- **Source-inspection branch:** resolve the right upstream/ref, then inspect source locally.
- **Multi-source claim branch:** collect factual claims, independently verify them, then deepen and synthesize.

Explicit repo/file/directory URLs use the source-inspection branch.

Do not use:

- for the current repo/worktree you are already in
- when the authoritative answer is product/account/runtime state rather than public source
- for a single-page web lookup that needs neither source inspection nor multi-source synthesis

## Source-inspection branch

First actions:

1. Identify or confirm the canonical upstream repo.
2. Resolve the exact ref that answers the user's question before reading code.
3. Clone or refresh `/tmp/agent-src/<owner>/<repo>`, then inspect locally at that ref.

### Procedure

#### 1) Resolve repo + ref with a small GitHub-first check

If the user already provided repo/file/directory URLs:

- extract owner/repo, ref, and path from those URLs
- use the repo page/search only as needed to confirm the canonical repo or default branch

If they did not provide a repo yet, identify it first. Prefer GitHub CLI:

- `gh search repos "<project name>" --limit 5`
- If you already have an owner/repo, skip search.

Do not start with raw content URLs or GitHub contents/tree APIs before you have resolved the repo/ref you intend to inspect.

#### 2) Clone into `/tmp` (and reuse it)

Pick a stable location:

- `/tmp/agent-src/<owner>/<repo>`

If it exists: reuse it and update it.

#### 3) Resolve the target ref before inspecting

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

#### 4) Search locally

If the user pointed at specific files/directories, start there inside the local checkout, then expand outward as needed.

Prefer fast, mechanical tools:

- `rg -n "<symbol|keyword>" .`
- `rg -n "functionName\\(" .`
- `rg -n "type .*<Name>|interface <Name>|class <Name>" .`

Use `git log -S` to find semantic changes:

- `git log -S "<string>" --oneline --decorate -- .`

#### 5) Use the web only after local source inspection when needed

Use web fetches for:

- docs that aren't in repo (`/docs`, wiki, website)
- issues/PR discussions
- release notes or changelogs not vendored in the repo

### Reuse rule

Keep the `/tmp/agent-src/...` clone around for reuse unless cleanup is explicitly requested.
Always run `git fetch --prune --tags` before relying on it.
Do not run `git pull` unless the user explicitly asks to update a local tracking branch.

Output:

- Report the repo and ref you actually inspected.
- If the user gave repo URLs, say how they mapped to the inspected repo/ref.
- Say explicitly when you needed web sources after local source inspection and why source alone was insufficient.

## Multi-source claim branch

Use this branch for comparisons, landscape research, papers, benchmarks, pricing, or any synthesis whose answer depends on multiple public factual claims.

### 1. Collect candidate claims

Keep claims atomic. For every candidate record:

- entity or subject
- one factual claim
- primary-source URL
- exact supporting quote
- finder identity and model family, when available

Every numeric literal in the claim must occur verbatim in that quote. No primary URL or exact quote means the claim remains unverified.
Reject the claim, not the entity or source. Done when every candidate has evidence or is explicitly unresolved.

### 2. Verify independently

A finder never verifies its own claim. Give a separate agent or fresh isolated context the claim and source, without the finder's rationale.
The verifier reopens the primary source, checks the quote and every number, and returns one verdict:

- `verified` — the primary source supports the claim as written
- `refuted` — the source contradicts or does not contain the claim
- `undecidable` — name the exact missing source or check

Use a different model family when the runtime exposes one. Otherwise use a distinct fresh agent and report `same-family (degraded)`.
If no independent context is available, keep the claim `undecidable`; do not relabel it verified.
Done when no candidate is awaiting a verifier.

### 3. Deepen, then synthesize

Deepening goes last. Give the deepening pass only verified claims plus the remaining gap list.
Any new claim from deepening returns to candidate collection and independent verification.
The final synthesis may use verified claims only; list unresolved gaps separately.
Done when every statement in the synthesis maps to a verified claim.

### 4. Persist selectively

Only verified claims may enter `,ai-kb`.
Store the primary URL in `--source`, include the exact quote in the body, identify the verifier with `--verified-by`, and set confidence honestly.
Refuted and undecidable claims remain task context, not durable knowledge.

Output:

- a compact claim table: claim, status, primary source, verifier
- synthesis based only on verified claims
- refuted claims and unresolved gaps, when material
