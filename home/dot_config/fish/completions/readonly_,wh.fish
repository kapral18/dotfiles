complete -c ,wh -f

complete -c ,wh -s h -l help -d 'Show help'

complete -c ,wh -n 'not __fish_seen_subcommand_from post get' -a post -d 'Send staged git patch'
complete -c ,wh -n 'not __fish_seen_subcommand_from post get' -a get -d 'Receive patch by wormhole code'
