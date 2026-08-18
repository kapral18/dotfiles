# Shared OpenRouter model/effort catalog for ,*-openrouter wrappers.
# GET /api/v1/models?supported_parameters=reasoning, cached 1h.
# A model stays listed when reasoning.supported_efforts is missing
# (live: inclusionai/ling-3.0-flash). Empty efforts use the full ladder.
# Offline/no-key falls back to the route-policy model trio.
set -g __openrouter_catalog_cache ~/.cache/,openrouter/models.tsv
set -g __openrouter_catalog_ttl 3600

function __openrouter_catalog_refresh
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
    mkdir -p (dirname $__openrouter_catalog_cache)
    python3 -c '
import json, sys
d = json.load(open(sys.argv[1]))
for m in d["data"]:
    efforts = (m.get("reasoning") or {}).get("supported_efforts") or []
    print(m["id"] + "\t" + ",".join(efforts))
' $tmp >$__openrouter_catalog_cache
    rm -f $tmp
end

function __openrouter_catalog_load
    if not test -f $__openrouter_catalog_cache
        __openrouter_catalog_refresh
    else
        # GNU stat (coreutils first on PATH here) uses -c %Y; BSD stat uses -f %m.
        set -l mtime (stat -c %Y $__openrouter_catalog_cache 2>/dev/null; or stat -f %m $__openrouter_catalog_cache 2>/dev/null)
        set -l age (math (date +%s) - $mtime)
        if test $age -gt $__openrouter_catalog_ttl
            __openrouter_catalog_refresh
        end
    end
    test -f $__openrouter_catalog_cache; and cat $__openrouter_catalog_cache
end

function __openrouter_catalog_models
    set -l rows (__openrouter_catalog_load)
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

function __openrouter_catalog_model
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

function __openrouter_catalog_efforts
    # Per-model catalog efforts, always union `none` (disables reasoning via workspace presets).
    set -l model (__openrouter_catalog_model)
    set -l rows (__openrouter_catalog_load)
    set -l efforts
    for r in $rows
        set -l parts (string split \t -- $r)
        if test "$parts[1]" = "$model"
            if test -z "$parts[2]"
                set efforts
            else
                set efforts (string split , -- $parts[2])
            end
            break
        end
    end
    if test (count $efforts) -eq 0
        # Unknown/free-form model: wrapper uses effort-<level>; offer the full ladder.
        set efforts none minimal low medium high xhigh max
    else if not contains -- none $efforts
        set efforts none $efforts
    end
    printf '%s\n' $efforts
end
