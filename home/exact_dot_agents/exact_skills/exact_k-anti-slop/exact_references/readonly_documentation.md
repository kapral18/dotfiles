# Technical documentation

Use for human-facing procedures, API/CLI reference, and code examples in the requested scope.
The README entry experience stays with `~/.agents/skills/k-readme/SKILL.md`; AI-facing instructions stay with `~/.agents/skills/k-writing-great-skills/SKILL.md`.
Do not impose a tutorial structure on a reference page or add sections merely to satisfy this checklist.

## Reader can complete the task

- Establish the starting state: required version, platform, working directory, dependencies, and permissions that actually affect the procedure.
  Put consequential prerequisites and destructive effects before the command that needs them.
- Order steps by dependency. Make optional branches explicit and give readers enough context to choose one.
  Link shared setup instead of copying it into several examples that can drift.
- Give an observable completion condition and explain material output.
  Distinguish an illustrative response from captured output; variable IDs, timestamps, or ordering must not look like exact guarantees.
- Describe a supported recovery for the documented failure, including whether work was saved.
  Do not prescribe retries when the operation might already have succeeded and repeating it could duplicate an effect.

## Examples and contracts

- Keep code and commands internally consistent with the documented version and platform.
  Include necessary imports/setup or link their location; mark excerpts and pseudocode as such.
- Separate copyable commands from prompts and output. Explain placeholders and quote arguments for the stated shell.
  Do not use a plausible production identifier or embedded credential as sample configuration.
- Verify flags, field names, paths, and linked symbols against the actual interface.
  Describe defaults, units, absent/null/empty distinctions, and error behavior when they affect use and are established by source.
  Do not turn implementation details into public guarantees.
- Keep examples, prose, and reference tables consistent.
  For generated reference pages, change the authoritative input rather than a generated copy.

Finish by tracing the example from its prerequisites to its result against the source.
Follow the SOP for execution; a documentation task does not authorize running a destructive or external example.
Distinguish source-checked examples from ones actually executed.

Sources: [Google procedure guidance](https://developers.google.com/style/procedures) and [code samples](https://developers.google.com/style/code-samples).
