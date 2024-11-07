# ------------------------------------
# Custom Functions
# ------------------------------------

## Function: get_risky_tests
function get_risky_tests --description "Get tests close to or beyond default Jest threshold"
    if test (count $argv) -eq 0
        echo "Usage: get_risky_tests <folder_path>"
        return
    end

    set temp_output (mktemp -t jest-output)

    cpulimit -l 2 -i -- node --max-old-space-size=12288 --trace-warnings scripts/jest $argv[1] \
        --runInBand --coverage=false --passWithNoTests --silent --ci --json --outputFile=$temp_output

    cat $temp_output | jq "
        .testResults[] as \$test |
        \$test.assertionResults[] |
        select(.duration > 4000) |
        {fullPath: \$test.name, fullName: .fullName, duration: .duration}
    "
end

function list_prs --description "List PRs using GitHub CLI"
    if test (count $argv) -eq 0
        gh pr list --limit 100 --json number,title --jq '.[] | "\(.number)\t\(.title)"' || true
    else
        gh pr list --search "$argv[1]" --json number,title --jq '.[] | "\(.number)\t\(.title)"' || true
    end
end

function get_pr_worktree --description "Fetch a PR from GitHub and create a worktree for it"
    if test (count $argv) -eq 0
        echo "Usage: get_pr_worktree <search_query>"
        return
    end

    # Search and select PR using fzf with improved preview
    set -l pr_number (gh pr list --search "$argv[1]" --json number,title \
        --jq '.[] | "\(.number) \(.title)"' | fzf --preview '
            gh pr view {1} --json number,title,body,author,labels,comments --template "
# PR #{{.number}}: {{.title}}

---

## Author: {{.author.login}}

{{range .labels}}- {{.name}} {{end}}

---


{{.body}}" | bat --style=auto --color always --wrap never --paging never --language Markdown
        ' --preview-window="right:70%:nowrap" --ansi | awk '{print $1}')

    if test -z "$pr_number"
        echo "No PR selected."
        return 1
    end

    # Fetch PR details using GitHub CLI
    set -l pr_info (gh pr view $pr_number --json headRefName,headRepository,headRepositoryOwner \
        --jq '.headRefName + " " + .headRepository.name + " " + .headRepositoryOwner.login')

    # Extract branch name, repository name, and owner
    set -l branch_name (echo $pr_info | cut -d ' ' -f1)
    set -l repo_name (echo $pr_info | cut -d ' ' -f2)
    set -l repo_owner (echo $pr_info | cut -d ' ' -f3)

    # Validate extracted information
    for var in branch_name repo_name repo_owner
        if test -z (eval echo \$$var)
            echo "$var is empty"
            return 1
        end
    end

    set -l repo_url "git@github.com:$repo_owner/$repo_name.git"

    # Add remote if it doesn't exist
    if not git remote get-url $repo_owner >/dev/null 2>&1
        git remote add $repo_owner $repo_url
    end

    # Fetch the branch
    git fetch $repo_owner $branch_name

    # Determine the main repository root directory
    set -l git_common_dir (git rev-parse --git-common-dir)
    set -l main_repo_root (dirname $git_common_dir)
    # Determine the parent directoary of the main repository root
    set -l parent_dir (dirname $main_repo_root)

    # Create the worktree in the parent directory
    # Set local branch to be able to do things like gh pr view --web
    git worktree add "$parent_dir/$repo_owner/$branch_name" -b "$branch_name" "$repo_owner/$branch_name"

    echo "Created worktree for PR #$pr_number on branch '$branch_name' from '$repo_owner'."

    zoxide add "$parent_dir/$repo_owner/$branch_name"
end

function remove_pr_worktree --description "Remove a worktree using fzf and delete the associated branch"
    set -l worktree (git worktree list -v | fzf --no-preview --ansi)

    if test -z "$worktree"
        echo "No worktree selected."
        return 1
    end

    set -l worktree_path (echo $worktree | awk '{print $1}')
    set -l worktree_branch (echo $worktree | awk '{
        last = $NF
        gsub(/^[[(]|[])]$/, "", last)
        print last
    }')

    zoxide remove $worktree_path

    git worktree remove $worktree_path

    # if the worktree_branch is HEAD then it's a detached HEAD
    # so we don't need to delete the branch
    if test $worktree_branch = HEAD
        echo "Removed worktree at '$worktree_path'."
        return
    end

    git branch -D $worktree_branch
end

## Function: appid
function appid --description "Get the application ID from the bundle identifier"
    if test (count $argv) -eq 0
        echo "Usage: appid <bundle_id>"
        return
    end

    set -l bundle_id $argv[1]
    set -l app_id (osascript -e "id of app \"$bundle_id\"")
    echo $app_id
end

## Function: dumputi
function dumputi --description "Dump list of Uniform Type Identifiers (UTIs)"
    /System/Library/Frameworks/CoreServices.framework/Versions/A/Frameworks/LaunchServices.framework/Versions/A/Support/lsregister -dump \
        | grep "uti:" \
        | awk '{print $2}' \
        | sort \
        | uniq
end

## Function: vid_ipad
function vid_ipad --description "Make video iPad-ready" -a input output
    ffmpeg -i $argv[1] -af "
        loudnorm=I=-14:TP=-1.5:LRA=7,
        acompressor=threshold=-20dB:ratio=4:attack=200:release=1000,
        equalizer=f=30:t=q:w=1:g=5
    " -c:v libx264 -crf 17 -preset slow -c:a aac -b:a 192k $argv[2]
end

## Function: get_source_for_llm
function get_source_for_llm --description "Get source code files for language models"
    fd -e ts -e tsx -E '*test*' -E '*mock*' -E 'setup_tests.ts' -E target --search-path $argv[1] -0 \
        | while read -lz file
        echo "===== $file ====="
        cat "$file"
        echo
    end | pbcopy
end

## Function: get_tests_for_llm
function get_tests_for_llm --description "Get test files for language models"
    fd -e ts -e tsx -p '(/mock/|/stub/|\.test\.)' -E 'setup_tests.ts' -E target --search-path $argv[1] -0 \
        | while read -lz file
        echo "===== $file ====="
        cat "$file"
        echo
    end | pbcopy
end

# ------------------------------------
# Deduplicate PATH
# ------------------------------------

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
