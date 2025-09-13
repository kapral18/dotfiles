complete -c f-disable-auto-merge --no-files -n '__fish_is_first_token' -a '(git branch -r | sed "s/.*\///")' -d "Base branch"

