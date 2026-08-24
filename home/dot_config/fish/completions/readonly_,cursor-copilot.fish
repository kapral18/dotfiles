set -g __cursor_copilot_cache ~/.cache/,cursor-copilot/models.tsv
set -g __cursor_copilot_ttl 3600

function __cursor_copilot_refresh
    set -l temp (mktemp)
    set -l adapter "$HOME/lib/,copilot-adapter/main.py"
    PYTHONPATH="$HOME/lib/,copilot-adapter" python3 "$adapter" __complete models >$temp 2>/dev/null; or begin
        rm -f $temp
        return 1
    end
    mkdir -p (dirname $__cursor_copilot_cache)
    mv $temp $__cursor_copilot_cache
end

function __cursor_copilot_rows
    if not test -f $__cursor_copilot_cache
        __cursor_copilot_refresh
    else
        set -l mtime (stat -c %Y $__cursor_copilot_cache 2>/dev/null; or stat -f %m $__cursor_copilot_cache 2>/dev/null)
        if test (math (date +%s) - $mtime) -gt $__cursor_copilot_ttl
            __cursor_copilot_refresh
        end
    end
    test -f $__cursor_copilot_cache; and cat $__cursor_copilot_cache
end

function __cursor_copilot_models
    for row in (__cursor_copilot_rows)
        string split -f1 \t -- $row
    end
end

function __cursor_copilot_model
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
    echo gpt-5.3-codex
end

function __cursor_copilot_values
    set -l column $argv[1]
    set -l selected (__cursor_copilot_model)
    for row in (__cursor_copilot_rows)
        set -l values (string split \t -- $row)
        if test "$values[1]" = "$selected"
            string split , -- $values[$column]
            return
        end
    end
end

complete -c ',cursor-copilot' -w ',cursor'
complete -c ',cursor-copilot' -s m -l model -d 'Select a live Copilot model' -x -a '(__cursor_copilot_models)'
complete -c ',cursor-copilot' -l effort -d 'Set selected model reasoning effort' -x -a '(__cursor_copilot_values 2)'
complete -c ',cursor-copilot' -l reasoning-effort -d 'Alias for --effort' -x -a '(__cursor_copilot_values 2)'
complete -c ',cursor-copilot' -l thinking -d 'Set Claude backend thinking' -x -a 'auto on off'
complete -c ',cursor-copilot' -l no-thinking -d 'Disable Claude backend thinking'
complete -c ',cursor-copilot' -l context -d 'Select selected model context tier' -x -a '(__cursor_copilot_values 3)'
complete -c ',cursor-copilot' -s h -l help -d 'Show wrapper help'
