# Model and effort candidates come from the live OpenRouter catalog
# (GET /api/v1/models?supported_parameters=reasoning), cached for 1h so completion stays fast.
# Each model's --effort list is its own `reasoning.supported_efforts`, so the two always match.
# Offline/no-key falls back to the route-policy trio.
set -g __cursor_openrouter_cache ~/.cache/,cursor-openrouter/models.tsv
set -g __cursor_openrouter_ttl 3600

function __cursor_openrouter_refresh
    set -l key $OPENROUTER_API_KEY
    if test -z "$key"; and command -q pass
        set key (pass show openrouter/api/token 2>/dev/null | string collect)
    end
    test -n "$key"; or return 1
    set -l tmp (mktemp)
    # --config - keeps the bearer token out of the process argv (ps-visible).
    printf 'header = "Authorization: Bearer %s"\n' $key | curl -sf -m 5 --config - \
        "https://openrouter.ai/api/v1/models?supported_parameters=reasoning" -o $tmp; or begin
        rm -f $tmp
        return 1
    end
    mkdir -p (dirname $__cursor_openrouter_cache)
    python3 -c '
import json, sys
d = json.load(open(sys.argv[1]))
for m in d["data"]:
    efforts = (m.get("reasoning") or {}).get("supported_efforts") or []
    if not efforts:
        continue
    print(m["id"] + "\t" + ",".join(efforts))
' $tmp >$__cursor_openrouter_cache
    rm -f $tmp
end

function __cursor_openrouter_load
    if not test -f $__cursor_openrouter_cache
        __cursor_openrouter_refresh
    else
        # GNU stat (coreutils first on PATH here) uses -c %Y; BSD stat uses -f %m.
        set -l mtime (stat -c %Y $__cursor_openrouter_cache 2>/dev/null; or stat -f %m $__cursor_openrouter_cache 2>/dev/null)
        set -l age (math (date +%s) - $mtime)
        if test $age -gt $__cursor_openrouter_ttl
            __cursor_openrouter_refresh
        end
    end
    test -f $__cursor_openrouter_cache; and cat $__cursor_openrouter_cache
end

function __cursor_openrouter_models
    set -l rows (__cursor_openrouter_load)
    if test (count $rows) -eq 0
        echo 'deepseek/deepseek-v4-flash-0731
moonshotai/kimi-k3
z-ai/glm-5.2
openai/gpt-5.6-terra'
        return
    end
    for r in $rows
        string split -f1 \t -- $r
    end
end

function __cursor_openrouter_model
    set -l tokens (commandline -opc)
    for i in (seq 2 (count $tokens))
        switch $tokens[$i]
            case '--model=*'
                string replace -- '--model=' '' $tokens[$i]
                return
            case -m --model
                set -l j (math $i + 1)
                if test $j -le (count $tokens)
                    echo $tokens[$j]
                end
                return
        end
    end
    echo deepseek/deepseek-v4-flash-0731
end

function __cursor_openrouter_efforts
    set -l model (__cursor_openrouter_model)
    set -l rows (__cursor_openrouter_load)
    for r in $rows
        set -l parts (string split \t -- $r)
        if test "$parts[1]" = "$model"
            string split , -- $parts[2]
            return
        end
    end
    # Unknown/free-form model: wrapper falls back to the model-agnostic effort-<level> preset.
    echo 'minimal
low
medium
high
xhigh
max'
end

complete -c ',cursor-openrouter' -f
complete -c ',cursor-openrouter' -s m -l model -x -a '(__cursor_openrouter_models)' -d 'OpenRouter model id (default deepseek/deepseek-v4-flash-0731)'
complete -c ',cursor-openrouter' -l effort -x -a '(__cursor_openrouter_efforts)' -d 'Reasoning effort (default max)'
complete -c ',cursor-openrouter' -l reasoning-effort -x -a '(__cursor_openrouter_efforts)' -d 'Alias for --effort'
complete -c ',cursor-openrouter' -l thinking -x -a '(__cursor_openrouter_efforts)' -d 'Alias for --effort'
complete -c ',cursor-openrouter' -l no-thinking -d 'Minimal reasoning effort'
complete -c ',cursor-openrouter' -l no-shim -d 'Direct OpenRouter route: skip the model guardrail and strict fix (only for preset-less models)'
complete -c ',cursor-openrouter' -l print -s p -d 'Print responses to console (non-interactive)'
complete -c ',cursor-openrouter' -l output-format -x -a 'text json stream-json' -d 'Output format (only with --print)'
complete -c ',cursor-openrouter' -l stream-partial-output -d 'Stream partial output as text deltas'
complete -c ',cursor-openrouter' -l mode -x -a 'plan ask' -d 'Start in the given execution mode'
complete -c ',cursor-openrouter' -l plan -d 'Start in plan mode'
complete -c ',cursor-openrouter' -l resume -x -d 'Select a session to resume'
complete -c ',cursor-openrouter' -l continue -d 'Continue previous session'
complete -c ',cursor-openrouter' -l force -s f -d 'Force allow commands unless explicitly denied'
complete -c ',cursor-openrouter' -l yolo -d 'Alias for --force'
complete -c ',cursor-openrouter' -l trust -d 'Trust the current workspace without prompting'
complete -c ',cursor-openrouter' -l help -s h -d 'Show Cursor Agent help'
