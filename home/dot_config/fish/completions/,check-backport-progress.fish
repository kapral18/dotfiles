if not functions -q __comma_is_completing_option
  function __comma_is_completing_option
    set -l cur (commandline -ct 2>/dev/null)
    test -n "$cur"; and string match -qr '^-+' -- $cur
  end
end

complete -c ,check-backport-progress -l merged-label -r -d 'Label identifying merged PRs needing backport' -n 'not __comma_is_completing_option' -a '(gh label list --limit 200 --json name --jq ".[].name" 2>/dev/null)'
complete -c ,check-backport-progress -l required-labels -r -d 'Space-separated required labels for open PRs' -n 'not __comma_is_completing_option' -a '(gh label list --limit 200 --json name --jq ".[].name" 2>/dev/null)'
complete -c ,check-backport-progress -l branches -r -d 'Space-separated target branches to check' -n 'not __comma_is_completing_option' -a '(git for-each-ref --format="%(refname:strip=2)" refs/heads refs/remotes 2>/dev/null)'
complete -c ,check-backport-progress -l upstream -r -d 'Name of the upstream git remote' -n 'not __comma_is_completing_option' -a '(git remote 2>/dev/null)'
complete -c ,check-backport-progress -s h -l help -d 'Show help'
