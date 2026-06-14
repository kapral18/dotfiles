complete -c ',gh-issuew' -f
complete -c ',gh-issuew' -s n -l number -d 'Print issue number'
complete -c ',gh-issuew' -s u -l url -d 'Print issue URL'
complete -c ',gh-issuew' -s h -l help -d 'Show help'
complete -c ',gh-issuew' -a '(__fish_git_branches)' -d 'Issue number, URL, or branch'
