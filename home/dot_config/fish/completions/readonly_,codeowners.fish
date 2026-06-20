complete -c ',codeowners' -f
complete -c ',codeowners' -s p -l paths-only -d 'Print only paths'
complete -c ',codeowners' -s o -l owner-of -d 'Print owner for path' -r -F
complete -c ',codeowners' -s h -l help -d 'Show help'
complete -c ',codeowners' -a '@elastic/kibana-management @elastic/kibana-core @elastic/kibana-security' -d 'Owner pattern'
