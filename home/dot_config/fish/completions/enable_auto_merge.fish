complete -c enable_auto_merge --no-files -n '__fish_is_first_token' -a '(git branch -r | sed "s/.*\///")' -d "Base branch"

