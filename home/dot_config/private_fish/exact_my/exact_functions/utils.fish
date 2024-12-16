function _get_worktree_parent_dir
    set -l git_common_dir (realpath (git rev-parse --git-common-dir))
    set -l main_repo_root (dirname $git_common_dir)
    dirname $main_repo_root
end

function _get_split_branch_name
    echo $argv[1] | string split -m 1 /
end

function _confirm
    read -P "Continue? [y/N] " reply
    echo
    string match -qr '^[Yy]$' -- $reply
end
