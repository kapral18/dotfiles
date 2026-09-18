# Completions for ,pi-model-profile.

# `default` is reserved (the repo's own Pi rows); the rest come from `pi_model_profiles`.
function __pi_model_profile_names
    echo default
    command -q chezmoi; or return 0
    command -q jq; or return 0
    chezmoi data --format json 2>/dev/null \
        | jq -r '.pi_model_profiles // {} | keys[]' 2>/dev/null
end

complete -c ,pi-model-profile -f

complete -c ,pi-model-profile -s h -l help -d 'Show usage'
complete -c ,pi-model-profile -l show -d 'Print the active profile and its rows without applying'
complete -c ,pi-model-profile -l list -d 'Print one profile name per line without applying'
complete -c ,pi-model-profile -l session -d 'Print <provider/model-id>\t<effort> for a profile without applying'

complete -c ,pi-model-profile -n 'not __fish_seen_argument -l show -l list' \
    -a '(__pi_model_profile_names)' -d 'Pi model profile'
