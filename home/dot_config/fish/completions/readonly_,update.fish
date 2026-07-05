set -l __update_categories dotfiles brew gh mise cargo yarn gems go uv manual selfupdaters

complete -c ',update' -f
complete -c ',update' -s n -l dry-run -d 'Show what would run'
complete -c ',update' -s o -l only -x -a "$__update_categories" -d 'Only update category'
complete -c ',update' -s s -l skip -x -a "$__update_categories" -d 'Skip category'
complete -c ',update' -s v -l verbose -d 'Show extra detail'
complete -c ',update' -s h -l help -d 'Show help'
