# Completions for ,llama-cpp.

function __llama_cpp_cp_host
    set -q LLAMA_CPP_HOST; and echo $LLAMA_CPP_HOST; and return
    echo 127.0.0.1
end

function __llama_cpp_cp_port
    set -q LLAMA_CPP_PORT; and echo $LLAMA_CPP_PORT; and return
    echo 8080
end

function __llama_cpp_cp_fetch_models
    command -q curl; or return 1
    command -q jq; or return 1
    set -l host (__llama_cpp_cp_host)
    set -l port (__llama_cpp_cp_port)
    set -l curl_args -fsS --max-time 1
    if set -q LLAMA_CPP_API_KEY
        set -a curl_args -H "Authorization: Bearer $LLAMA_CPP_API_KEY"
    end
    curl $curl_args "http://$host:$port/models" 2>/dev/null
end

function __llama_cpp_cp_ids
    __llama_cpp_cp_fetch_models \
        | jq -r '.data[]? | "\(.id)\t\(.status.value)"' 2>/dev/null
end

function __llama_cpp_cp_ids_loaded
    __llama_cpp_cp_fetch_models \
        | jq -r '.data[]? | select(.status.value == "loaded") | "\(.id)\tloaded"' 2>/dev/null
end

set -l __llama_cpp_cp_subs serve run stop status load unload help

complete -c ',llama-cpp' -f

complete -c ',llama-cpp' -n "not __fish_seen_subcommand_from $__llama_cpp_cp_subs" \
    -a serve -d 'Start llama-server in router mode'
complete -c ',llama-cpp' -n "not __fish_seen_subcommand_from $__llama_cpp_cp_subs" \
    -a run -d 'Run a command with a shared router lease'
complete -c ',llama-cpp' -n "not __fish_seen_subcommand_from $__llama_cpp_cp_subs" \
    -a stop -d 'Stop the lifecycle-owned router'
complete -c ',llama-cpp' -n "not __fish_seen_subcommand_from $__llama_cpp_cp_subs" \
    -a status -d 'Show router models and load state'
complete -c ',llama-cpp' -n "not __fish_seen_subcommand_from $__llama_cpp_cp_subs" \
    -a load -d 'Load a model'
complete -c ',llama-cpp' -n "not __fish_seen_subcommand_from $__llama_cpp_cp_subs" \
    -a unload -d 'Unload a model'
complete -c ',llama-cpp' -n "not __fish_seen_subcommand_from $__llama_cpp_cp_subs" \
    -a help -d 'Show usage'

complete -c ',llama-cpp' -n '__fish_seen_subcommand_from load' \
    -a '(__llama_cpp_cp_ids)'

complete -c ',llama-cpp' -n '__fish_seen_subcommand_from run' \
    -a '(__fish_complete_subcommand --fcs-skip=2)'

complete -c ',llama-cpp' -n '__fish_seen_subcommand_from stop' \
    -s f -l force -d 'Interrupt active consumers and stop the owned router'

complete -c ',llama-cpp' -n '__fish_seen_subcommand_from unload' \
    -a '(__llama_cpp_cp_ids_loaded)'
complete -c ',llama-cpp' -n '__fish_seen_subcommand_from unload' \
    -s a -l all -d 'Unload every loaded model'
