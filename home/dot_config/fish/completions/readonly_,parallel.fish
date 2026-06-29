complete -c ',parallel' -s h -l help -d "Show help"
complete -c ',parallel' -l version -d "Show version"
complete -c ',parallel' -s j -d "Run n jobs in parallel" -r
complete -c ',parallel' -s k -d "Keep output in input order"
complete -c ',parallel' -s X -d "Multiple arguments with context replace"
complete -c ',parallel' -s S -d "Use sshlogin" -r
complete -c ',parallel' -l colsep -d "Split input on regexp for positional replacements" -r
complete -c ',parallel' -l slf -d "Use an sshloginfile" -r
complete -c ',parallel' -l trc -d "Transfer, return, and clean up files" -r
complete -c ',parallel' -l onall -d "Run command with argument on all sshlogins"
complete -c ',parallel' -l nonall -d "Run command with no arguments on all sshlogins"
complete -c ',parallel' -l pipe -d "Split standard input to multiple jobs"
complete -c ',parallel' -l recend -d "Record end separator for --pipe" -r
complete -c ',parallel' -l recstart -d "Record start separator for --pipe" -r
complete -c ',parallel' -l line-buffer -d "Buffer output by line"
complete -c ',parallel' -l plus -d "Enable extended replacement strings"
