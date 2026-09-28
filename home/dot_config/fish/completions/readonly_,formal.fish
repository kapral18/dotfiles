# Completions for ,formal 0.1.0.

set -l __formal_subcommands doctor init anchors build explore mutate traces replay prove audit status catalog
set -l __formal_anchors_subcommands add check list
set -l __formal_catalog_subcommands list resolve checkout stale uncovered save gc
set -l __formal_tiers F2 F3
set -l __formal_trace_modes cover failures
# `--json` is only ever registered on a leaf subparser (`_add_json_flag` in cli.py never runs on
# the bare `anchors`/`catalog` group parsers) -- offering it right after `anchors`/`catalog`,
# before a leaf like `add`/`list` is chosen, would suggest a flag the real CLI rejects.
set -l __formal_leaf_subcommands doctor init build explore mutate traces replay prove audit status \
    $__formal_anchors_subcommands $__formal_catalog_subcommands

complete -c ',formal' -f

complete -c ',formal' -n __fish_use_subcommand -l version -d 'Show version'

complete -c ',formal' -n "not __fish_seen_subcommand_from $__formal_subcommands" \
    -a doctor -d 'Check elan/lake/lean and the pinned toolchain'
complete -c ',formal' -n "not __fish_seen_subcommand_from $__formal_subcommands" \
    -a init -d 'Create a unit work dir from the template or a saved version'
complete -c ',formal' -n "not __fish_seen_subcommand_from $__formal_subcommands" \
    -a anchors -d 'Manage anchors for a unit'
complete -c ',formal' -n "not __fish_seen_subcommand_from $__formal_subcommands" \
    -a build -d 'lake build the unit'
complete -c ',formal' -n "not __fish_seen_subcommand_from $__formal_subcommands" \
    -a explore -d 'Exhaustively search reachable states for property violations'
complete -c ',formal' -n "not __fish_seen_subcommand_from $__formal_subcommands" \
    -a mutate -d 'Run the control and each mutant step function'
complete -c ',formal' -n "not __fish_seen_subcommand_from $__formal_subcommands" \
    -a traces -d 'Write traces/traces.jsonl'
complete -c ',formal' -n "not __fish_seen_subcommand_from $__formal_subcommands" \
    -a replay -d 'Feed traces to a real-code adapter and compare observed output'
complete -c ',formal' -n "not __fish_seen_subcommand_from $__formal_subcommands" \
    -a prove -d 'Forbidden-token scan plus collectAxioms on every Proofs theorem'
complete -c ',formal' -n "not __fish_seen_subcommand_from $__formal_subcommands" \
    -a audit -d "Aggregate gate over the tier's required stages"
complete -c ',formal' -n "not __fish_seen_subcommand_from $__formal_subcommands" \
    -a status -d "Show every unit's state for the current repo"
complete -c ',formal' -n "not __fish_seen_subcommand_from $__formal_subcommands" \
    -a catalog -d 'Persistent per-machine unit-version catalog'

# doctor
complete -c ',formal' -n '__fish_seen_subcommand_from doctor' -l install -d 'Install the pinned Lean toolchain'

# init
complete -c ',formal' -n '__fish_seen_subcommand_from init' -l tier -x -a "$__formal_tiers" -d 'Verification tier (default F2)'
complete -c ',formal' -n '__fish_seen_subcommand_from init' -l design \
    -d 'Design unit: models intended behavior before code exists'
complete -c ',formal' -n '__fish_seen_subcommand_from init' -l from-version -r \
    -d 'Materialize a saved version instead of the template'

# anchors add|check|list
complete -c ',formal' -n "__fish_seen_subcommand_from anchors; and not __fish_seen_subcommand_from $__formal_anchors_subcommands" \
    -a add -d 'Record an exact-text anchor snippet'
complete -c ',formal' -n "__fish_seen_subcommand_from anchors; and not __fish_seen_subcommand_from $__formal_anchors_subcommands" \
    -a check -d 'Resolve every anchor against the current tree'
complete -c ',formal' -n "__fish_seen_subcommand_from anchors; and not __fish_seen_subcommand_from $__formal_anchors_subcommands" \
    -a list -d 'List anchors for a unit'
complete -c ',formal' -n '__fish_seen_subcommand_from add' -l id -r \
    -d 'Explicit anchor id, such as A1; re-anchors it if the id already exists'
complete -c ',formal' -n '__fish_seen_subcommand_from add' -l note -r -d 'Free-text note'
complete -c ',formal' -n '__fish_seen_subcommand_from check' -l write \
    -d 'Persist relocated start/end for every unchanged anchor'

# build
complete -c ',formal' -n '__fish_seen_subcommand_from build' -l proofs -d 'Also build Unit.Proofs'

# explore
complete -c ',formal' -n '__fish_seen_subcommand_from explore' -l max-states -x -d 'Non-negative state budget override'
complete -c ',formal' -n '__fish_seen_subcommand_from explore' -l max-depth -x -d 'Non-negative depth budget override'

# mutate
complete -c ',formal' -n '__fish_seen_subcommand_from mutate' -l max-states -x -d 'Non-negative state budget override'
complete -c ',formal' -n '__fish_seen_subcommand_from mutate' -l max-depth -x -d 'Non-negative depth budget override'

# traces
complete -c ',formal' -n '__fish_seen_subcommand_from traces' -l mode -x -a "$__formal_trace_modes" -d 'Trace selection mode'
complete -c ',formal' -n '__fish_seen_subcommand_from traces' -l max -x -d 'Non-negative maximum traces (cover mode default 500)'

# replay
complete -c ',formal' -n '__fish_seen_subcommand_from replay' -l adapter -r \
    -d 'Adapter shell command (overrides MANIFEST.adapter.cmd)'
complete -c ',formal' -n '__fish_seen_subcommand_from replay' -l against -x \
    -d 'Differential mode: compare REF vs HEAD on the same traces'

# audit
complete -c ',formal' -n '__fish_seen_subcommand_from audit' -l require -x -d 'Comma-separated stage override'
complete -c ',formal' -n '__fish_seen_subcommand_from audit' -l allow-unverified-conformance \
    -d 'Allow verdict pass when replay is unverified'

# catalog list|resolve|checkout|stale|uncovered|save|gc
complete -c ',formal' -n "__fish_seen_subcommand_from catalog; and not __fish_seen_subcommand_from $__formal_catalog_subcommands" \
    -a list -d 'List units and versions'
complete -c ',formal' -n "__fish_seen_subcommand_from catalog; and not __fish_seen_subcommand_from $__formal_catalog_subcommands" \
    -a resolve -d 'Resolve the newest valid version for a unit'
complete -c ',formal' -n "__fish_seen_subcommand_from catalog; and not __fish_seen_subcommand_from $__formal_catalog_subcommands" \
    -a checkout -d "Materialize the resolved version into this branch's work dir"
complete -c ',formal' -n "__fish_seen_subcommand_from catalog; and not __fish_seen_subcommand_from $__formal_catalog_subcommands" \
    -a stale -d 'List units with any non-unchanged anchor'
complete -c ',formal' -n "__fish_seen_subcommand_from catalog; and not __fish_seen_subcommand_from $__formal_catalog_subcommands" \
    -a uncovered -d 'List changed hunks not overlapped by any anchor'
complete -c ',formal' -n "__fish_seen_subcommand_from catalog; and not __fish_seen_subcommand_from $__formal_catalog_subcommands" \
    -a save -d 'Save the current unit snapshot as a catalog version'
complete -c ',formal' -n "__fish_seen_subcommand_from catalog; and not __fish_seen_subcommand_from $__formal_catalog_subcommands" \
    -a gc -d 'Drop old versions and orphan kit dirs'

complete -c ',formal' -n '__fish_seen_subcommand_from checkout' -l force \
    -d 'Discard local work-dir differences from the resolved version instead of refusing'
complete -c ',formal' -n '__fish_seen_subcommand_from stale' -l base -x -d 'Restrict to units anchoring files changed since REF'
complete -c ',formal' -n '__fish_seen_subcommand_from uncovered' -l base -x -d 'Diff base (required)'
complete -c ',formal' -n '__fish_seen_subcommand_from save' -l allow-unverified -d 'Save without a passing audit'
complete -c ',formal' -n '__fish_seen_subcommand_from gc' -l keep -x -d 'Non-negative versions to keep per unit (default 5)'

# --json on every leaf subcommand (not the bare `anchors`/`catalog` group commands)
complete -c ',formal' -n "__fish_seen_subcommand_from $__formal_leaf_subcommands" -l json -d 'Print the receipt as JSON'
