# Completions for ,proof.

set -l __proof_subcommands start path add-criterion add-evidence show review block resolve-blocker status check report
set -l __proof_evidence_types test build lint typecheck diff screenshot browser log file-read manual-user-confirmation
set -l __proof_verdicts supports does-not-support unclear

complete -c ',proof' -f

for subcommand in $__proof_subcommands
    complete -c ',proof' -n "not __fish_seen_subcommand_from $__proof_subcommands" -a $subcommand
end

complete -c ',proof' -l version -d 'Show version'
complete -c ',proof' -l workspace -r -d 'Workspace path'
complete -c ',proof' -l topic -r -d 'Proof topic'
complete -c ',proof' -n "__fish_seen_subcommand_from $__proof_subcommands" -l workspace -r -d 'Workspace path'
complete -c ',proof' -n "__fish_seen_subcommand_from $__proof_subcommands" -l topic -r -d 'Proof topic'

complete -c ',proof' -n '__fish_seen_subcommand_from start' -l force -d 'Replace current proof ledger'

complete -c ',proof' -n '__fish_seen_subcommand_from add-criterion' -l id -r -d 'Criterion id'
complete -c ',proof' -n '__fish_seen_subcommand_from add-criterion' -l requires -x -a "$__proof_evidence_types" -d 'Required evidence type'

complete -c ',proof' -n '__fish_seen_subcommand_from add-evidence review' -s c -l criterion -r -d 'Criterion id'
complete -c ',proof' -n '__fish_seen_subcommand_from add-evidence' -s t -l type -x -a "$__proof_evidence_types" -d 'Evidence type'
complete -c ',proof' -n '__fish_seen_subcommand_from add-evidence' -l command -r -d 'Command to run or record'
complete -c ',proof' -n '__fish_seen_subcommand_from add-evidence' -l artifact-path -r -d 'Artifact to copy into proof state'
complete -c ',proof' -n '__fish_seen_subcommand_from add-evidence' -l exit-code -r -d 'Exit code for external command evidence'
complete -c ',proof' -n '__fish_seen_subcommand_from add-evidence' -l summary -r -d 'Evidence summary'

complete -c ',proof' -n '__fish_seen_subcommand_from review' -s e -l evidence -r -d 'Evidence id'
complete -c ',proof' -n '__fish_seen_subcommand_from review' -s v -l verdict -x -a "$__proof_verdicts" -d 'Review verdict'
complete -c ',proof' -n '__fish_seen_subcommand_from review' -s n -l notes -r -d 'Review notes'
complete -c ',proof' -n '__fish_seen_subcommand_from review' -l reviewer -r -d 'Reviewer name'

complete -c ',proof' -n '__fish_seen_subcommand_from status check' -l json -d 'Print JSON'
complete -c ',proof' -n '__fish_seen_subcommand_from status' -s v -l verbose -d 'Print gate issues'
