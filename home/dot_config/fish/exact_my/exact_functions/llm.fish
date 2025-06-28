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
    set -l search_paths $argv
    if test (count $search_paths) -eq 0
        set search_paths .
    end

    fd -t f $search_paths -0 $exclude_args \
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
