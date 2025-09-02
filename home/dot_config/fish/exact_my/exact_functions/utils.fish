# Get the parent directory of the current git repository
# This is used to organize worktrees in a consistent location
function _get_worktree_parent_dir
    set -l git_common_dir (realpath (git rev-parse --git-common-dir))
    set -l main_repo_root (dirname $git_common_dir)
    dirname $main_repo_root
end

function _get_split_branch_name
    if test (count $argv) -eq 0
        echo "Error: _get_split_branch_name requires a branch name argument" >&2
        return 1
    end
    echo $argv[1] | string split -m 1 /
end

function _confirm
    read -P "Continue? [y/N] " reply
    echo
    string match -qr '^[Yy]$' -- $reply
end

function _safe_exec_cmd
    set -l cmd $argv
    set -l output (eval $cmd ^ /dev/stderr)
    set -l status $status
    if test $status -ne 0
        echo "Error executing command: $cmd" >&2
        echo "Output: $output" >&2
        return 1
    end
    echo $output
end
