function fuzzy_brew_search --description "Search for a package and add it to the Brewfile"
    set -l query $argv[1]

    if test -z "$query"
        echo "Usage: fuzzy_brew_search <search_term>"
        return 1
    end

    set -l selected (
        brew search --desc --eval-all $query |
        grep ':' |
        awk -F: '{print $1}' |
        fzf --preview 'brew info {1}' \
            --bind 'ctrl-b:execute(brew info {1} | grep -o '\''https\?://[^ ]*'\'' | head -1 | xargs open)' \
            --header 'Tab: select, Ctrl+B: open homepage, Esc: cancel'
    )

    if test -n "$selected"

        # gum choose to choose whether for "personal" "work" or "all" use
        set -l scope (
            gum choose "personal only" "work only" "both personal/work"
        )

        crush run "add $selected to .Brewfile for $scope scope. To avoid guessing wrong package always brew info that package to make sure it's the correct one. If ambiguous ask"
    else
        echo "No package selected"
    end
end
