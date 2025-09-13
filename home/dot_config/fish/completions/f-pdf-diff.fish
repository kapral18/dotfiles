complete -c f-pdf-diff -s d -d "Set image density (default: 300)" -r
complete -c f-pdf-diff -s f -d "Set output format (default: pdf)" -r
complete -c f-pdf-diff -s o -d "Set output file name" -r -a "(__fish_complete_suffix .pdf)"
# Positional arguments: two PDF files
complete -c f-pdf-diff -n 'not __fish_seen_subcommand_from -d --no-files -o' -a "(__fish_complete_suffix .pdf)"
