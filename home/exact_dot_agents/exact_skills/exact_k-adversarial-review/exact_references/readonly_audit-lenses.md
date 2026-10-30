# Whole-solution audit lenses

Evaluate every lens against the inventory in `~/.agents/skills/k-adversarial-review/SKILL.md`.
Mark a lens inapplicable only with a source-based reason.
These are investigation prompts, not evidence of a defect, mandatory technology choices, or a finding quota.
Use the quality references selected by the main skill for each surface.

## Goal, architecture, and complexity

- Trace the advertised outcome to a complete implementation.
  Where does a feature exist only as a flag, placeholder, mock, doc claim, or unused backend?
- Identify the owner of each domain rule and durable fact; check for conflicting rules and independently writable copies of derived state.
- Examine dependency direction, module boundaries, and change locality.
  Which ordinary change requires coordinated edits across unrelated modules, and what actual contract forces that coupling?
- Check whether interfaces hide complexity or merely forward it; identify wrappers, factories, registries, plugin seams, options, and compatibility paths without a current requirement or consumer.
- For each proposed simplification, name the behavior that survives and the dependency/branch/state that disappears.
  Few callers alone do not disprove an abstraction's value.
- Trace the cost of questionable machinery: divergent rules, impossible states, repeated work, hidden effects, difficult recovery, or misleading interfaces.
  A stylistic preference is not an architectural finding.

## Implementation, state, and operations

- Trace creation, updates, deletion, retries, and recovery on the same object.
  Check both operation orders where they can interact; identify the invariant preventing duplicates, resurrection, partial writes, and stale results.
- Inspect parsing, normalization, defaults, units, encoding, paths/symlinks, and empty/absent/null distinctions at the actual boundaries.
  Does validation happen before every relevant use?
- Follow errors to their caller and user-visible result.
  Look for success reported after failure, swallowed exceptions, unbounded retry, retry after an irreversible effect, and fallback to insecure or misleading behavior.
- Compare supported roles, platforms, deployment contexts, and entry points for paths bypassing the primary entry point's guard.
- Check resource ownership and lifecycle: cancellation, cleanup, partial initialization, interrupted writes, background tasks, transactions, and rollback.
  Validate permissions and destinations before destructive work.
- Derive scale concerns from a concrete supported workload and algorithm or resource bound.
  Identify unbounded queues, scans, allocation, recursion, or repeated I/O; do not invent latency measurements or hypothetical hyperscale requirements.

## Security and privacy

- Map actor → untrusted input → trust boundary → sensitive sink → enforcing control.
  Include anonymous users, authenticated users, other tenants, local files/config, remote content, and CI contributors only where exposed.
- Trace authentication separately from authorization: object ownership, tenant scope, privilege checks, sessions/tokens, logout/revocation, and alternate endpoints.
  A hidden button or client-side check cannot enforce a server boundary.
- Follow strings and structured inputs into shell/process arguments, SQL, templates/HTML, deserialization, URLs, file paths, and archives.
  Determine the exact escaping/parameterization and reachable context before claiming injection, traversal, SSRF, or XSS.
- Inspect secret references and data flows through logs, analytics, telemetry, caches, error messages, exports, and artifacts.
  Report where sensitive data can escape and to whom, without emitting its contents.
- Read install/build/release and CI trust boundaries: untrusted pull-request code, inherited credentials, workflow permissions, downloaded executables, mutable dependencies/actions, artifact provenance, and package lifecycle scripts.
- Check TLS, cryptography, cookie/session policy, defaults, and external-service assumptions against exact configuration and dependency contracts.
  Never invent vulnerabilities from package names or stale memory.
- When evaluating a dependency advisory, establish the resolved version, authoritative affected range, and reachable use.
  An advisory database's silence does not establish security; do not fetch a live scan as part of verification.
- Distinguish a confirmed embedded credential/private-data exposure from an unverified secret-shaped string.
  Do not try a credential to test validity.
  For a confirmed exposure, recommend removal plus revocation/rotation; deleting the current file does not remove reachable history.

## Product, visual quality, and accessibility

- Trace the primary user job, navigation, destructive decisions, completion feedback, and recovery.
  Identify where the user cannot tell what happened, what failed, or what to do next.
- Check loading, empty, partial, stale, error, permission-denied, disabled, and success states where the product can enter them.
  Flag only states with a reachable trigger and a concrete usability consequence.
- Inspect semantics, keyboard/focus handling, accessible names, forms, control states, responsive constraints, overflow, localization, and motion using the matching shared quality references.
- Compare the actual information hierarchy and copy with the product's content and decisions.
  Look for placeholder metrics, fabricated proof, decorative controls, repetitive cards, and styling that obscures important actions or data.
- A gradient, typeface, rounded card, icon, animation, or familiar layout alone proves no defect and no AI origin.
  Describe the loss of meaning, consistency, accessibility, or task completion.
- Separate defects visible in supplied local screenshots/assets from risks supported by code.
  Mark visual composition and interactive behavior unverified where source cannot settle them and rendered evidence is missing.
  Do not launch a browser to fill the gap.
- Apply the product lens to CLI, APIs, and libraries through help/errors, examples, contracts, and caller recovery.
  Mark the visual lens inapplicable for surfaces with no visual output.

## Tests, comments, and claimed assurance

- Map existing behavioral protection to the core invariants and failure boundaries.
  Does a test observe the public result with an independent oracle, or merely repeat implementation constants and mocked return values?
- Compare fakes with contracts for real commands, filesystems, clocks, frameworks, and external responses;
  identify mismatches that invalidate claimed protection.
- Check whether setup, cleanup, imports, hooks, and runners can overwrite user data, mutate real configuration, read real credentials, or start real services.
  Inspect tests without running unsafe ones.
- Identify material behaviors missing durable protection, including invariants repeatedly fixed without a protecting test.
  Recommend the smallest necessary behavioral coverage, not a count or a case for every branch/incident.
- Identify redundant assertions, snapshots pinning private structure or prose, and scaffolding that increases maintenance without protecting distinct behavior.
  Preserve required directives and useful behavioral coverage.
- Require comments to carry legal/tooling requirements or a critical non-obvious constraint.
  Flag misleading promises and commentary replacing finished code; never demand explanatory narration as a default remedy.
- Compare "tested," "secure," "accessible," "production-ready," performance, and compatibility claims with actual evidence.
  Credit checks only for the paths and contracts they cover.

## Public-release readiness

- Establish what publishing exposes: tracked tree, reachable history and tags intended for publication, examples, fixtures, screenshots, generated bundles/maps, package contents, and build artifacts available locally.
  Exclude private machine files outside the publication surface. Report unavailable release material as a coverage gap.
- Inspect those surfaces with secret-safe methods for credentials, personal/internal data, proprietary content, machine-specific identifiers, and accidental test artifacts.
  `.gitignore` does not remove tracked files or historical content.
- Check the project's license and third-party notices against the code/assets actually distributed.
  Flag concrete missing or conflicting terms, cite their text, and distinguish unresolved legal interpretation from an established packaging omission.
- Trace a new user's documented path from prerequisites through install/configuration to the first useful result and removal.
  Check copyable commands, default permissions, destructive effects, undeclared tools, absolute personal paths, and unsupported platform assumptions from source.
- Compare package exports, included files, executable bits, generated artifacts, source maps, and release/build configuration with documented use.
  Check that the shipped artifact contains what consumers require and exposes no private content.
- Check operational promises against configuration, migration/recovery paths, data retention, and failure reporting.
  A repository does not need a service's operational infrastructure unless its supported use requires it.
- Separate a concrete blocker from a product preference.
  No badge, roadmap, contribution guide, CI provider, container, or enterprise feature is mandatory merely because the repo will be public.
