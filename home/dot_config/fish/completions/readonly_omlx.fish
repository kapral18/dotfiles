# Completions for the oMLX CLI (https://github.com/jundot/omlx).
#
# Model names for `--model` / `--pin` are the union (deduped by id) of:
#   1. live `GET http://$OMLX_HOST:$OMLX_PORT/v1/models` on the running server
#      (preferred description — matches model aliases and loaded downloads)
#   2. filesystem scan of ${OMLX_MODELS_ROOT:-$HOME/.omlx/models}, filtered to
#      directories that contain a `config.json` (same "complete" check as
#      scripts/sync_omlx_models.py in this dotfiles repo)
#
# The union matters because oMLX only discovers on-disk models at server
# startup (engine_pool.discover_models). A model downloaded after
# `omlx serve` launched won't appear in /v1/models until the server is
# restarted or `POST /api/reload` is hit, but it should still be a valid
# completion target.

function __omlx_host
    set -q OMLX_HOST; and echo $OMLX_HOST; and return
    echo 127.0.0.1
end

function __omlx_port
    set -q OMLX_PORT; and echo $OMLX_PORT; and return
    echo 8000
end

function __omlx_models_root
    set -q OMLX_MODELS_ROOT; and echo $OMLX_MODELS_ROOT; and return
    echo $HOME/.omlx/models
end

function __omlx_models_from_server
    command -q curl; or return 1
    command -q jq; or return 1
    set -l host (__omlx_host)
    set -l port (__omlx_port)
    # Tight timeout so completion never stalls if the server is unreachable.
    set -l json (curl -fsS --max-time 1 "http://$host:$port/v1/models" 2>/dev/null)
    or return 1
    printf '%s\n' $json | jq -r '.data[]? | "\(.id)\t\(.model_type // "loaded")"' 2>/dev/null
end

function __omlx_models_from_disk
    set -l root (__omlx_models_root)
    test -d $root; or return 1
    for dir in $root/*/
        set -l name (basename $dir)
        if test -f $dir/config.json
            printf '%s\ton disk\n' $name
        end
    end
end

function __omlx_models
    # Union server + disk, deduped by the id field (before the first tab).
    # Server is emitted first so its description (model_type / "loaded")
    # wins over the disk "on disk" placeholder when the same id appears in
    # both sources.
    set -l seen
    for line in (__omlx_models_from_server) (__omlx_models_from_disk)
        set -l id (string split -m 1 \t -- $line)[1]
        test -n "$id"; or continue
        if not contains -- $id $seen
            set -a seen $id
            printf '%s\n' $line
        end
    end
end

# Default: no file completion. Specific flags (like --model-dir) override.
complete -c omlx -f

# ------------------------------------------------------------------------------
# Top-level subcommands
# ------------------------------------------------------------------------------
complete -c omlx -n __fish_use_subcommand -a serve -d 'Start the OpenAI-compatible multi-model server'
complete -c omlx -n __fish_use_subcommand -a launch -d 'Configure and launch an external coding tool (codex / opencode / openclaw / pi)'
complete -c omlx -n __fish_use_subcommand -a diagnose -d 'Run diagnostics (menubar, server)'

# ------------------------------------------------------------------------------
# omlx launch <tool>
# ------------------------------------------------------------------------------
set -l __omlx_launch_tools codex opencode openclaw pi list

complete -c omlx -n "__fish_seen_subcommand_from launch; and not __fish_seen_subcommand_from $__omlx_launch_tools" \
    -a codex -d 'OpenAI Codex CLI (npm i -g @openai/codex)'
complete -c omlx -n "__fish_seen_subcommand_from launch; and not __fish_seen_subcommand_from $__omlx_launch_tools" \
    -a opencode -d 'OpenCode TUI (curl -fsSL https://opencode.ai/install | bash)'
complete -c omlx -n "__fish_seen_subcommand_from launch; and not __fish_seen_subcommand_from $__omlx_launch_tools" \
    -a openclaw -d 'OpenClaw agent (npm i -g openclaw)'
complete -c omlx -n "__fish_seen_subcommand_from launch; and not __fish_seen_subcommand_from $__omlx_launch_tools" \
    -a pi -d 'Pi coding agent (npm i -g @mariozechner/pi-coding-agent)'
complete -c omlx -n "__fish_seen_subcommand_from launch; and not __fish_seen_subcommand_from $__omlx_launch_tools" \
    -a list -d 'Show available integrations and install status'

# Flags for `omlx launch`
complete -c omlx -n '__fish_seen_subcommand_from launch' \
    -l model -x -a '(__omlx_models)' \
    -d 'Model id (live server -> ~/.omlx/models fallback)'
complete -c omlx -n '__fish_seen_subcommand_from launch' -l host -x -d 'oMLX server host (default: 127.0.0.1)'
complete -c omlx -n '__fish_seen_subcommand_from launch' -l port -x -d 'oMLX server port (default: 8000)'
complete -c omlx -n '__fish_seen_subcommand_from launch' -l api-key -x -d 'oMLX API key'
complete -c omlx -n '__fish_seen_subcommand_from launch; and __fish_seen_subcommand_from openclaw' \
    -l tools-profile -x -a 'coding full allowlist' \
    -d 'OpenClaw tool profile (coding/full = unrestricted exec)'

# ------------------------------------------------------------------------------
# omlx serve
# ------------------------------------------------------------------------------
complete -c omlx -n '__fish_seen_subcommand_from serve' \
    -l model-dir -r -F \
    -d 'Directory containing model subdirectories'
complete -c omlx -n '__fish_seen_subcommand_from serve' \
    -l pin -x -a '(__omlx_models)' \
    -d 'Comma-separated model ids to preload / pin in memory'
complete -c omlx -n '__fish_seen_subcommand_from serve' -l host -x -d 'Listen host (default: 127.0.0.1)'
complete -c omlx -n '__fish_seen_subcommand_from serve' -l port -x -d 'Listen port (default: 8000)'
complete -c omlx -n '__fish_seen_subcommand_from serve' -l max-model-memory -x -d 'Max memory budget for loaded models (e.g. 32GB)'
complete -c omlx -n '__fish_seen_subcommand_from serve' -l max-process-memory -x -d 'Hard process memory ceiling (e.g. 48GB or auto)'
complete -c omlx -n '__fish_seen_subcommand_from serve' -l max-concurrent-requests -x -d 'Max concurrent requests (BatchGenerator)'
complete -c omlx -n '__fish_seen_subcommand_from serve' -l mcp-config -r -F -d 'MCP tools config JSON path'
