complete -c ,wh -f

complete -c ,wh -s h -l help -d 'Show help'

complete -c ,wh -n 'not __fish_seen_subcommand_from send recv' -a send -d 'Send staged diff, a file/dir, the clipboard, or stdin'
complete -c ,wh -n 'not __fish_seen_subcommand_from send recv' -a recv -d 'Receive: apply patch, load clipboard, or save file/dir'

complete -c ,wh -n '__fish_seen_subcommand_from send' -l clip -d 'Send the clipboard (text or image)'
complete -c ,wh -n '__fish_seen_subcommand_from send' -F

complete -c ,wh -n '__fish_seen_subcommand_from recv' -s o -l output -d 'Destination dir, or patch target' -r -F
complete -c ,wh -n '__fish_seen_subcommand_from recv' -l save -d 'Save a received clipboard payload instead of loading it'
