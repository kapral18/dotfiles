function __complete_es_data_folders
    # List only directory names (not full paths) from the es_data folder
    set -l es_data_path "$HOME/work/kibana/es_data"
    if test -d "$es_data_path"
        for dir in "$es_data_path"/*
            if test -d "$dir"
                basename "$dir"
            end
        end
    end
end

complete -c ,kbn-stack -l es -d "Elasticsearch backend" -x -a "snapshot serverless"
complete -c ,kbn-stack -l project-type -d "Serverless project type" -x -a "es security oblt"
complete -c ,kbn-stack -l data -d "ES data folder name under ~/work/kibana/es_data" -x -a "(__complete_es_data_folders)"
complete -c ,kbn-stack -l slot -d "Force a specific slot number" -x
complete -c ,kbn-stack -l detach -d "Agent mode: background ES+Kibana, wait until ready, record started_by=agent"
complete -c ,kbn-stack -l stop -d "Tear down this worktree's stack (recorded pids or interactive port owners) and drop its registry entry"
complete -c ,kbn-stack -l stop-all -d "Tear down registered detached/serverless stacks; leave pid-less interactive tmux entries"
complete -c ,kbn-stack -s E -d "Extra Elasticsearch setting (key=value)" -x
complete -c ,kbn-stack -s K -l kbn -d "Extra Kibana setting passed to yarn start as --key=value" -x
complete -c ,kbn-stack -s h -l help -d "Show help"
