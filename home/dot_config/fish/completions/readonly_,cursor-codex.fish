function __cursor_codex_rows
    set -l cache "$HOME/.codex/models_cache.json"
    test -f "$cache"; or return
    python3 -c '
import json
import sys

try:
    models = json.load(open(sys.argv[1], encoding="utf-8")).get("models", [])
except (OSError, ValueError):
    raise SystemExit(1)
for model in models:
    slug = model.get("slug")
    efforts = model.get("supported_reasoning_levels", [])
    if isinstance(slug, str):
        print(slug + "\t" + ",".join(item.get("effort", "") for item in efforts if isinstance(item, dict)))
' "$cache"
end

function __cursor_codex_models
    for row in (__cursor_codex_rows)
        string split -f1 \t -- $row
    end
end

function __cursor_codex_model
    set -l tokens (commandline -opc)
    for i in (seq 2 (count $tokens))
        switch $tokens[$i]
            case '--model=*'
                string replace -- '--model=' '' $tokens[$i]
                return
            case -m --model
                set -l value (math $i + 1)
                if test $value -le (count $tokens)
                    echo $tokens[$value]
                end
                return
        end
    end
    PYTHONPATH="$HOME/lib/,codex-adapter" python3 -c 'import main; print(main.resolve_default_model())' 2>/dev/null
end

function __cursor_codex_efforts
    set -l selected (__cursor_codex_model)
    for row in (__cursor_codex_rows)
        set -l values (string split \t -- $row)
        if test "$values[1]" = "$selected"
            string split , -- $values[2]
            return
        end
    end
end

complete -c ',cursor-codex' -w ',cursor'
complete -c ',cursor-codex' -s m -l model -x -a '(__cursor_codex_models)' -d 'Override Codex backend model'
complete -c ',cursor-codex' -l effort -x -a '(__cursor_codex_efforts)' -d 'Override selected-model reasoning effort'
complete -c ',cursor-codex' -l reasoning-effort -x -a '(__cursor_codex_efforts)' -d 'Override selected-model reasoning effort'
complete -c ',cursor-codex' -s h -l help -d 'Show Codex subscription wrapper help'
