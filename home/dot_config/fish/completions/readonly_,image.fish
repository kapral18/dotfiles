# Completions for ,image.

set -l __image_subs sync status

complete -c ',image' -f

complete -c ',image' -n "not __fish_seen_subcommand_from $__image_subs" \
    -a sync -d 'Download FLUX.2 klein 9B weights (~15 GB)'
complete -c ',image' -n "not __fish_seen_subcommand_from $__image_subs" \
    -a status -d 'Show sd-cli and weight paths'

complete -c ',image' -n "not __fish_seen_subcommand_from $__image_subs" \
    -s i -l image -d 'Input image (edit only; repeatable)' -r
complete -c ',image' -n "not __fish_seen_subcommand_from $__image_subs" \
    -s p -l prompt -d 'Generate or edit instruction (or pass as the positional prompt)' -x
complete -c ',image' -n "not __fish_seen_subcommand_from $__image_subs" \
    -s o -l output -d 'Output path' -r
complete -c ',image' -n "not __fish_seen_subcommand_from $__image_subs" \
    -l width -d 'Generate canvas width (omit for sd-cli 512; edit follows the input)' -x
complete -c ',image' -n "not __fish_seen_subcommand_from $__image_subs" \
    -l height -d 'Generate canvas height (omit for sd-cli 512; edit follows the input)' -x
complete -c ',image' -n "not __fish_seen_subcommand_from $__image_subs" \
    -l steps -d 'Diffusion steps (default: 4)' -x
complete -c ',image' -n "not __fish_seen_subcommand_from $__image_subs" \
    -l cfg -d 'CFG scale (default: 1.0)' -x
complete -c ',image' -n "not __fish_seen_subcommand_from $__image_subs" \
    -l seed -d 'Optional RNG seed' -x
complete -c ',image' -n "not __fish_seen_subcommand_from $__image_subs" \
    -l dry-run -d 'Print sd-cli argv and exit'
complete -c ',image' -s h -l help -d 'Show help'
complete -c ',image' -l version -d 'Show version'
