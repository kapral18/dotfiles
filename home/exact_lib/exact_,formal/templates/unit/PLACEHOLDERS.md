# Placeholders

Every `@@...@@` token used anywhere under `templates/unit/`. The `,formal` CLI's `init`
subcommand substitutes these (plain text replacement) when materializing a unit's work dir from
this template; nothing under `templates/unit/` should be used un-substituted.

| placeholder         | used in                              | substituted with                                                                                            |
| ------------------- | ------------------------------------ | ----------------------------------------------------------------------------------------------------------- |
| `@@KIT_PATH@@`      | `lakefile.toml` (`[[require]] path`) | absolute path to this unit's copy of `FormalKit` (`<root>/_kit/<kit-hash>`)                                 |
| `@@UNIT@@`          | `MANIFEST.json` (`unit`)             | the unit name                                                                                               |
| `@@TIER@@`          | `MANIFEST.json` (`tier`)             | `"F2"` or `"F3"`                                                                                            |
| `@@REPO_ID@@`       | `MANIFEST.json` (`repo_id`)          | the repo id (first 16 hex of sha256 of the git common dir)                                                  |
| `@@BRANCH@@`        | `MANIFEST.json` (`branch`)           | the current branch (or `detached-<shortsha>`)                                                               |
| `@@SOURCE_COMMIT@@` | `MANIFEST.json` (`source_commit`)    | `git rev-parse HEAD` at unit creation time                                                                  |
| `@@KIT_HASH@@`      | `MANIFEST.json` (`kit_hash`)         | the `FormalKit` copy's content hash (matches the `_kit/<kit-hash>` directory name `@@KIT_PATH@@` points at) |
