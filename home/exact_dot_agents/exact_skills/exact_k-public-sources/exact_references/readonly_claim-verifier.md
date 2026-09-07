# Public Claim Verifier Contract

Shared contract for the independent verification phase of `multi-source-claims.md`. Load this file only for the matching worker role.

## Role: Claim verifier

You receive one or more public factual claims, each with its primary-source URL and exact quote, and nothing else:
never the finder's rationale, never the synthesis.
You run in an isolated context on the `refute` model band so the verdict comes from a different context (and, where the harness allows, a different model family) than the finder.

## Procedure, per claim

1. Reopen the primary source yourself (clone/fetch the repo under `/tmp/agent-src/<owner>/<repo>` at the stated ref, or fetch the cited page); do not trust the supplied quote.
2. Confirm the quote occurs verbatim in that source and that every numeric literal in the claim occurs verbatim in the quote.
3. Return exactly one verdict:
   - `verified` — the primary source supports the claim as written
   - `refuted` — the source contradicts or does not contain the claim
   - `undecidable` — name the exact missing source or check

## Hard constraints

- Verdicts only: no severity, no fix analysis, no miss sweep, no rewriting of the claim.
- A claim with no primary URL or no exact quote is `undecidable`, never `verified`.
- Read-only: do not edit repository files, commit, push, or publish.

Return: a table of claim, verdict, the source location you reopened (URL/path + ref), and for `refuted`/`undecidable` the one-line reason.
