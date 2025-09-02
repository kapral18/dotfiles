# Function to deduplicate PATH
function dedup_path
    set -l unique_paths
    for dir in $PATH
        if not contains $dir $unique_paths
            set unique_paths $unique_paths $dir
        end
    end
    set -gx PATH $unique_paths
end
