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

complete --no-files --exclusive --command start-main-kbn --condition __fish_is_first_token --arguments '(__complete_es_data_folders)'
