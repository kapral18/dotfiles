# Completions for ,omlx (model-level control plane).
#
# Subcommands and positional args are context-aware:
#   ,omlx <TAB>          → status / load / unload / help
#   ,omlx status <TAB>   → (no positional)
#   ,omlx load <TAB>     → union of discovered-unloaded ids (from server) and
#                          disk-only ids (from ~/.omlx/models). The `,omlx load`
#                          script itself will refuse disk-only ids with a
#                          server-restart hint, but tabbing them is still
#                          useful so the user can see what's "almost there".
#   ,omlx unload <TAB>   → currently-loaded model ids only (+ --all flag) —
#                          loaded is a server-only state, so no disk fallback.

function __omlx_cp_host
    set -q OMLX_HOST; and echo $OMLX_HOST; and return
    echo 127.0.0.1
end

function __omlx_cp_port
    set -q OMLX_PORT; and echo $OMLX_PORT; and return
    echo 8000
end

function __omlx_cp_models_root
    set -q OMLX_MODELS_ROOT; and echo $OMLX_MODELS_ROOT; and return
    echo $HOME/.omlx/models
end

function __omlx_cp_fetch_status
    command -q curl; or return 1
    command -q jq; or return 1
    set -l host (__omlx_cp_host)
    set -l port (__omlx_cp_port)
    set -l curl_args -fsS --max-time 1
    if set -q OMLX_API_KEY
        set -a curl_args -H "Authorization: Bearer $OMLX_API_KEY"
    end
    curl $curl_args "http://$host:$port/v1/models/status" 2>/dev/null
end

function __omlx_cp_ids_from_disk
    set -l root (__omlx_cp_models_root)
    test -d $root; or return 0
    for dir in $root/*/
        if test -f $dir/config.json
            printf '%s\n' (basename $dir)
        end
    end
end

function __omlx_cp_ids_loaded
    __omlx_cp_fetch_status \
        | jq -r '.models[]? | select(.loaded == true) | "\(.id)\tloaded (~\(.estimated_size / 1073741824 | floor) GB)"' 2>/dev/null
end

# Union: server-known unloaded (preferred description with size + engine type)
# plus disk-only ids the server hasn't discovered yet. The `,omlx load`
# command distinguishes the two at runtime.
function __omlx_cp_ids_unloaded_union
    set -l status_json (__omlx_cp_fetch_status)
    set -l server_ids (printf '%s' "$status_json" | jq -r '.models[]?.id' 2>/dev/null)

    printf '%s' "$status_json" \
        | jq -r '.models[]? | select(.loaded == false) | "\(.id)\ton disk (~\(.estimated_size / 1073741824 | floor) GB)"' 2>/dev/null

    for id in (__omlx_cp_ids_from_disk)
        if not contains -- $id $server_ids
            printf '%s\ton disk, not discovered — restart server to load\n' $id
        end
    end
end

set -l __omlx_cp_subs status load unload help

complete -c ',omlx' -f

complete -c ',omlx' -n "not __fish_seen_subcommand_from $__omlx_cp_subs" \
    -a status -d 'Show loaded/unloaded models + memory usage'
complete -c ',omlx' -n "not __fish_seen_subcommand_from $__omlx_cp_subs" \
    -a load -d 'Load a model into memory (warmup via /v1/chat/completions)'
complete -c ',omlx' -n "not __fish_seen_subcommand_from $__omlx_cp_subs" \
    -a unload -d 'Unload a model (POST /v1/models/<id>/unload)'
complete -c ',omlx' -n "not __fish_seen_subcommand_from $__omlx_cp_subs" \
    -a help -d 'Show usage'

complete -c ',omlx' -n '__fish_seen_subcommand_from load' \
    -a '(__omlx_cp_ids_unloaded_union)'

complete -c ',omlx' -n '__fish_seen_subcommand_from unload' \
    -a '(__omlx_cp_ids_loaded)'
complete -c ',omlx' -n '__fish_seen_subcommand_from unload' \
    -s a -l all -d 'Unload every model currently loaded'
