complete -c ',mise-bump' -f
complete -c ',mise-bump' -a '(mise ls --global --current 2>/dev/null | string match -r "^\S+")' -d 'mise tool'
complete -c ',mise-bump' -s h -l help -d 'Show help'
