function cp_files_for_llm --description 'Prepare files for language models'
    argparse 'E/exclude=+' -- $argv
    or return

    set -l exclude_args
    if set -q _flag_exclude
        for pattern in $_flag_exclude
            set exclude_args $exclude_args --exclude "$pattern"
        end
    end

    # Use remaining arguments as search paths, default to current directory
    set -l search_path $argv[1]
    if test (count $argv) -eq 0
        set search_path .
    end

    fd -t f -0 $exclude_args . "$search_path" \
        | while read -lz file
        if file --mime-type "$file" | grep -q text/
            echo
            echo "# File: ===== $file ====="
            echo

            cat "$file"
            echo
        end
    end | pbcopy
end
