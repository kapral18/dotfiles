set -l __palantir_subcommands summon farsee behold send-word answer grant routed banish keep-watch trial statusline doctor composer state dashboard
set -l __palantir_state_subs ls new show set paths doctor
set -l __palantir_composer_subs classify strip idle

function __palantir_legions
    ,palantir state ls --json 2>/dev/null | python3 -c "
import json,sys
try:
    rows = json.load(sys.stdin)
except Exception:
    rows = []
for r in rows:
    print(f\"{r.get('id','')}\t{r.get('stage','')}: {r.get('goal','')[:50]}\")
" 2>/dev/null
end

complete -c ,palantir -f
complete -c ,palantir -n "not __fish_seen_subcommand_from $__palantir_subcommands" -a summon -d 'Summon a legion (worktree + tmux session + coordinator + supervisor)'
complete -c ,palantir -n "not __fish_seen_subcommand_from $__palantir_subcommands" -a farsee -d 'Survey all legions (stage, attention, criteria)'
complete -c ,palantir -n "not __fish_seen_subcommand_from $__palantir_subcommands" -a behold -d 'Behold one legion: stage + supervisor liveness'
complete -c ,palantir -n "not __fish_seen_subcommand_from $__palantir_subcommands" -a send-word -d 'Send composer-guarded word to a role window'
complete -c ,palantir -n "not __fish_seen_subcommand_from $__palantir_subcommands" -a answer -d 'Answer a holding condition and resume its stored stage'
complete -c ,palantir -n "not __fish_seen_subcommand_from $__palantir_subcommands" -a grant -d 'Grant a cleared_for_human legion'
complete -c ,palantir -n "not __fish_seen_subcommand_from $__palantir_subcommands" -a routed -d "Mark a closed legion's memory packet as routed"
complete -c ,palantir -n "not __fish_seen_subcommand_from $__palantir_subcommands" -a banish -d 'Banish a legion (fail-closed; --force overrides)'
complete -c ,palantir -n "not __fish_seen_subcommand_from $__palantir_subcommands" -a keep-watch -d "Keep or stop the legion's supervisor watch"
complete -c ,palantir -n "not __fish_seen_subcommand_from $__palantir_subcommands" -a trial -d 'Put acceptance criteria to machine trial'
complete -c ,palantir -n "not __fish_seen_subcommand_from $__palantir_subcommands" -a statusline -d 'tmux status-right fragment'
complete -c ,palantir -n "not __fish_seen_subcommand_from $__palantir_subcommands" -a doctor -d 'Check dependencies and state home'
complete -c ,palantir -n "not __fish_seen_subcommand_from $__palantir_subcommands" -a composer -d 'Pane composer classifier'
complete -c ,palantir -n "not __fish_seen_subcommand_from $__palantir_subcommands" -a state -d 'Legion manifest I/O'
complete -c ,palantir -n "not __fish_seen_subcommand_from $__palantir_subcommands" -a dashboard -d 'Open the seeing-stone dashboard'

# summon flags
complete -c ,palantir -n '__fish_seen_subcommand_from summon' -l base -r -d 'base ref for the worktree'
complete -c ,palantir -n '__fish_seen_subcommand_from summon' -l criteria -r -d 'acceptance criteria JSON'
complete -c ,palantir -n '__fish_seen_subcommand_from summon' -l no-worktree -d 'run in the current directory'

# legion-id positionals
complete -c ,palantir -n '__fish_seen_subcommand_from behold send-word answer grant routed banish keep-watch trial' -a '(__palantir_legions)' -d legion
complete -c ,palantir -n '__fish_seen_subcommand_from send-word' -l window -r -d 'target role window (default: command)'
complete -c ,palantir -n '__fish_seen_subcommand_from banish' -l force -d 'override fail-closed checks'
complete -c ,palantir -n '__fish_seen_subcommand_from keep-watch' -l stop -d 'stop the running supervisor'

# farsee / state / composer subs
complete -c ,palantir -n '__fish_seen_subcommand_from farsee' -l json -d 'JSON output'
complete -c ,palantir -n '__fish_seen_subcommand_from state; and not __fish_seen_subcommand_from '"$__palantir_state_subs" -a "$__palantir_state_subs" -d 'state subcommand'
complete -c ,palantir -n '__fish_seen_subcommand_from state; and __fish_seen_subcommand_from show set paths' -a '(__palantir_legions)' -d legion
complete -c ,palantir -n '__fish_seen_subcommand_from composer; and not __fish_seen_subcommand_from '"$__palantir_composer_subs" -a "$__palantir_composer_subs" -d 'composer subcommand'
complete -c ,palantir -s h -l help -d 'Show help'
