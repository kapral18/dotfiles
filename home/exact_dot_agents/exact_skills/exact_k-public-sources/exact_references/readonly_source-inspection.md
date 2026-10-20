# Source inspection

## Source-inspection branch

Identify the canonical upstream and question-specific ref before reading code;
clone or refresh `/tmp/agent-src/<owner>/<repo>`, then inspect that ref locally.

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
- If the user did not specify a ref, use the locally installed version's ref when the question is about local behavior, otherwise the default branch;
  say which, and name the other ref that could change the answer.

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

If the user pointed at specific files/directories, start there (as `<dir>`) inside the local checkout, then expand outward as needed.
Otherwise list the top-level layout first (`ls`, or `git -c core.quotePath=false ls-files | cut -d/ -f1-2 | sort -u`), pick the source directory as `<dir>`, and widen to sibling source directories when it has no hit.

Use the harness search tool scoped to `<dir>` first; the shell `rg` equivalents are:

- `rg -n "<symbol|keyword>" <dir>`
- `rg -n "functionName\\(" <dir>`
- `rg -n "type .*<Name>|interface <Name>|class <Name>" <dir>`

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
