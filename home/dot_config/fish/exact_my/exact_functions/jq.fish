function search_brew_desc -d "Search through Homebrew package descriptions"
    if test (count $argv) -eq 0
        echo "Error: Please provide a search term"
        echo "Usage: search_brew_desc SEARCH_TERM"
        return 1
    end

    brew info --json=v2 --installed | jq -r --arg SEARCH "$argv[1]" '.formulae | map(select(.desc | ascii_downcase | contains($SEARCH | ascii_downcase)) | {name, desc, homepage})'
end
