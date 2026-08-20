# Agent reasoning failure modes

This is a catalog of agent conduct failures that have happened in real sessions on this machine, kept short and load-bearing. Each entry names a single failure mode, the falsifier that would have caught it, and the system change that prevents its recurrence. The list is intentionally small: anti-patterns grouped by category.

This catalog is not a skill: it has no procedure to invoke. Its consumer is the canonical `AGENTS.md` §2.1b (Self-Claims), where the SOP delegates "before asserting a claim, name what would make it false and check that." When a session reproduces one of the modes below, the SOP already mandates the falsifier; sessions load this file by path so the falsifier is at hand when needed.

## Identity / Repository resolution

### Identity mismatch hallucination

**Mode.** Session runs `gh pr view 284530` (or similar) and gets `Could not resolve to a PullRequest`. The agent concludes "no such PR exists" or "the repo isn't authed" without verifying `gh auth status`.

**Falsifier.** Run `gh auth status` once per session start. The authenticated principal is a fact, not a hypothesis.

**Prevention.** `~/.agents/hooks/session_context.py` injects a `### GitHub identity` line at the top of every SessionStart context block, populated from `gh api user --jq .login` with a 2-second timeout. The line is plain text and fails open — empty output means `gh` was unavailable, not that auth failed.

### PR number misread

**Mode.** The branch suffix `259250` is read as a PR number; `gh pr view 259250` returns "could not resolve"; the agent falls back to "no PR, review the local branch" without trying the standard `gh pr view` (no args) or `,gh-prw` fallbacks.

**Falsifier.** `,gh-prw` already probes the current branch + commit SHA and is the first check. If it cannot resolve the user's claim, the k-github `Targeting` fallback chain runs: `gh pr view --repo OWNER/REPO <n>` → `gh pr view` (no args) → `gh pr view --head <branch>` → `gh issue view <n>`.

**Prevention.** `k-github/SKILL.md` Targeting section documents the chain and explicitly warns against declaring "no PR exists" before step 5.

## Verdict prematureness

### Merge-ready verdict without reviewer-thread triage

**Mode.** Agent states "merge-ready, no surviving findings" on the first response of a PR review, without reading the live reviewer conversations, the inline reviewer comments, or the PR's CI check enumeration.

**Falsifier.** A `Verdict:` line is only honest after `gh pr checks`, the GraphQL reviewThreads pull, and the per-comment author-type classification have all completed on the current head SHA.

**Prevention.** `k-review/SKILL.md` adds a "Verdict Gate" section that names those three checks as the precondition for any verdict; earlier responses are required to be status ledgers without the verdict word.

## Probe budget

### Probe-budget exhaustion

**Mode.** Agent runs 5+ probe commands (mostly Jest or `node -e`) and they all return "fail" because the agent's mental model of the artifact under test is wrong (regex arithmetic off-by-one, harness envelope shapes different from memory, etc.). The agent keeps probing instead of re-reading the source. Observed with minimax-m3, which itself proposed this ledger mechanism after exhibiting the loop; sessions on that model are the population to check when auditing whether the ledger gets written.

**Falsifier.** Reading the source once beats a fifth probe. Specifically for the pattern of "an assertion about how the code behaves keeps returning the opposite of what I expect" — the answer is "go read the source, character by character if needed."

**Prevention.** `~/.agents/hooks/correction_detector.py` carries a `probe-budget-exhausted` signal: it reads a session-scoped JSONL ledger (`/tmp/specs/<workspace>/<session_key>.probe-ledger.jsonl`) and returns the signal when 3+ of the last 8 entries have `result == "fail"`. The companion `,probe` helper at `~/bin/,probe` records the entries via `,probe pass "<summary>"` / `,probe fail "<summary>"`. The session-injected `[VERIFICATION DISCIPLINE]` prefix (`~/.config/tmux/agent_prompts/prefix.txt`) carries the recording instruction, so the producer side is wired on every harness. When the per-turn `perturn_recall.py` hook sees the signal, it injects a "re-read the source" note on the next prompt.

The helper resolves the session key through `,agent-memory status --json`, passing the harness session id when `CLAUDE_SESSION_ID` / `CODEX_SESSION_ID` / `CURSOR_SESSION_ID` / `COPILOT_AGENT_SESSION_ID` is set. Antigravity shell probes call `,agent-memory status` without a session id and use its active-topic resolution; Pi/OMP probes can fall back to an `ad-hoc` ledger, which remains useful while debugging a regex.

## Argument-by-tool vs. argument-by-text

### Refusing a direct tool directive in prose

**Mode.** The user issues a single-tool directive (e.g. "just run `gh pr view`", "trust me, try without args"). The agent argues in prose about why the tool might not work, listing edge cases, instead of running the requested tool first.

**Falsifier.** Directives are inputs. The right response is to run the directive, report what the tool returned, and only then explain the result. If the tool returns a failure, that is evidence to share, not a hypothesis to defend before the run.

**Prevention.** No automated hook today; flagged by `correction_detector.py`'s explicit-claim patterns ("you guessed", "instead of testing"). The agents that fall into this mode produce a recognizable verb-heavy prose paragraph before any tool call; that signature is what the user has historically flagged with "are you stupid". Treat the flag as a system bug, not as a personal attack.

## Source-claim drift

### Stating external behavior without anchoring

**Mode.** Agent names a third-party API contract, OS behavior, or library parameter set from memory rather than reading the artifact, and proceeds on the remembered shape. Examples in this session: Monaco `IKeyboardEvent` semantics (verified live with `web_search`), keycode-vs-key handling (verified against MDN spec), Bash `set -e` and `NOMATCH` interaction.

**Falsifier.** SOP §2.1 "Resolve identity before semantics" already mandates this. Anchoring means: read the source, run a probe, or quote a fetched doc with the exact verbatim phrase. Anything cited from memory is a claim, and a claim about external behavior is a 2.1b self-claim too.

**Prevention.** The SOP already enforces this; no setup change needed beyond acknowledging that the failure mode repeats and adding it to this index so a session can search it when the user reports it.

## Tool-name fidelity

### Comma-CLI name stripped in prose

**Mode.** User commands are comma-prefixed executables (`~/bin/,gh-prw`, `,probe`, `,ai-kb`). A session runs `,gh-prw` correctly in argv yet writes `gh-prw` in chat prose and tool-call descriptions, normalizing the leading comma away as punctuation because the remainder looks like a `gh` helper. The same slip pairs with flag mashing: `--json` passed to `,gh-prw`, whose surface is `--number`/`--url` only (observed in a Cursor session, 2026-08-19).

**Falsifier.** The helper's `--help` and `k-github/SKILL.md` spell the name verbatim; a comma-less mention contradicts source already in context. For flags, SOP §2.1 already mandates reading `--help` before use.

**Prevention.** `prefix.txt` carries "User commands are comma-prefixed executables: the leading comma … is part of the command — type it verbatim" (added 2026-08-19), injected at session start and reinforced per turn.

## Hook surface debt

### Premise_nudge misses its target

**Mode.** Premise-nudge fires when the agent fires a destructive or premise-bearing command (e.g. `git stash`, `git clean -fd`, `--force` push). It rides an `additionalContext` note along with the call so the nudge lands at the step that depends on the premise rather than at the end of the turn. A blocked command would be worse than an unverified one, so the hook does **not** block.

**Falsifier.** The premise is part of the command in `premise_nudge.py`'s PREMISE_PATTERNS tuple. Patterns miss when a verb is added (e.g. a new git flag) or the harness envelope differs.

**Prevention.** When premise-nudge fails to fire on what looked like a destructive command, append the missing verb and a matching pattern to PREMISE_PATTERNS; the hook is intentionally pattern-additive.

## Operating rules

- One entry per failure mode. If a session produces a new shape, add an entry; do not generalize this catalog until three distinct sessions exhibit the shape.
- Each entry starts with the **Mode**, names the **Falsifier**, and points at the **Prevention** (system change). When there is no prevention, the entry is a research note, not a closed loop.
- This catalog does not have a single "best practices" section on purpose; the SOP already owns best practices. The catalog's job is to anchor recurring failure shapes so the SOP can refer to them.
