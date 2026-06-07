complete -c ,wh -f

complete -c ,wh -s h -l help -d 'Show help'

complete -c ,wh -n 'not __fish_seen_subcommand_from post get' -a post -d 'Send staged diff, or a file/dir path'
complete -c ,wh -n 'not __fish_seen_subcommand_from post get' -a get -d 'Receive: apply patch or save file/dir'

complete -c ,wh -n '__fish_seen_subcommand_from post' -F

complete -c ,wh -n '__fish_seen_subcommand_from get' -s o -l output -d 'Destination dir, or patch target' -r -F
