function grepo --description 'Grep for a string in files and open the results in fzf'
    set -l editor_cmd "$EDITOR +/$argv[1] +'norm! n'"
    rg -l "$argv[1]" | fzf --bind "enter:execute($editor_cmd {})" --preview "bat --style=numbers --color=always {}"
end
