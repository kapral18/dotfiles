complete -c ',gh-prw' -f
complete -c ',gh-prw' -s n -l number -d 'Print PR number'
complete -c ',gh-prw' -s u -l url -d 'Print PR URL'
complete -c ',gh-prw' -s h -l help -d 'Show help'
complete -c ',gh-prw' -a '(__fish_git_branches)' -d 'PR number, URL, or branch'
