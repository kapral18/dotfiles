# Completions for ,probe.
#
# Mirrors the contract documented in home/exact_bin/executable_,probe:
#   ,probe pass "<short summary>"
#   ,probe fail "<short summary>"
#   ,probe fail "<short summary>" --reason "<reason>"
#
# --reason is also valid after a `pass` (the script accepts it for both).

set -l __probe_results pass fail

complete -c ',probe' -f

complete -c ',probe' -n "not __fish_seen_subcommand_from $__probe_results" -a pass -d 'Record a probe attempt that confirmed the model'
complete -c ',probe' -n "not __fish_seen_subcommand_from $__probe_results" -a fail -d 'Record a probe attempt that contradicted the model'

complete -c ',probe' -n "__fish_seen_subcommand_from $__probe_results" -l reason -r -d 'Why the probe failed (or other short note)'
