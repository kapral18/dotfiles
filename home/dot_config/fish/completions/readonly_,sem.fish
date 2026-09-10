# Print an optspec for argparse to handle cmd's options that are independent of any subcommand.
function __fish_sem_global_optspecs
    string join \n h/help V/version
end

function __fish_sem_needs_command
    # Figure out if the current invocation already has a command.
    set -l cmd (commandline -opc)
    set -e cmd[1]
    argparse -s (__fish_sem_global_optspecs) -- $cmd 2>/dev/null
    or return
    if set -q argv[1]
        # Also print the command, so this can be used to figure out what it is.
        echo $argv[1]
        return 1
    end
    return 0
end

function __fish_sem_using_subcommand
    set -l cmd (__fish_sem_needs_command)
    test -z "$cmd"
    and return 1
    contains -- $cmd[1] $argv
end

complete -c ',sem' -n __fish_sem_needs_command -s h -l help -d 'Print help'
complete -c ',sem' -n __fish_sem_needs_command -s V -l version -d 'Print version'
complete -c ',sem' -n __fish_sem_needs_command -f -a diff -d 'Show semantic diff of changes (supports git diff syntax). Untracked files are excluded, matching git behavior'
complete -c ',sem' -n __fish_sem_needs_command -f -a impact -d 'Show impact of changing an entity (deps, dependents, transitive impact, tests)'
complete -c ',sem' -n __fish_sem_needs_command -f -a find -d 'Find entity definitions by name — answers from the mmap query index when one exists (cold-process, <10ms on a large repo); falls back to a fresh build otherwise, which then leaves an index for next time'
complete -c ',sem' -n __fish_sem_needs_command -f -a callers -d 'Show direct callers of an entity (who calls/references it) — the index\'s reverse postings, same freshness/fallback discipline as `find`'
complete -c ',sem' -n __fish_sem_needs_command -f -a refs -d 'Show direct refs of an entity (what it calls/references) — the index\'s forward postings, same freshness/fallback discipline as `find`'
complete -c ',sem' -n __fish_sem_needs_command -f -a grep -d 'Search file text — rg-compatible `file:line:text` output, served from the mmap query index\'s trigram postings when one exists (cold process, target <50ms on a large repo); falls back to a plain scan otherwise. Pattern is always a regex (same default as rg without `-F`); patterns with no usable trigram (e.g. `-i`, short literals, unconstrained alternation) degrade to an honest full scan rather than a wrong answer'
complete -c ',sem' -n __fish_sem_needs_command -f -a graph -d 'Show the full entity dependency graph'
complete -c ',sem' -n __fish_sem_needs_command -f -a blame -d 'Show semantic blame — who last modified each entity'
complete -c ',sem' -n __fish_sem_needs_command -f -a hook -d 'Internal plumbing for agent-harness hooks (hidden)'
complete -c ',sem' -n __fish_sem_needs_command -f -a log -d 'Show evolution of an entity through git history, or, with no entity, the repo\'s history analytics: hotspots and co-change pairs'
complete -c ',sem' -n __fish_sem_needs_command -f -a entities -d 'List entities under one or more file or directory paths'
complete -c ',sem' -n __fish_sem_needs_command -f -a context -d 'Show token-budgeted context for an entity'
complete -c ',sem' -n __fish_sem_needs_command -f -a stats -d 'Show lifetime diff statistics'
complete -c ',sem' -n __fish_sem_needs_command -f -a mcp -d 'Start the MCP server (stdin/stdout transport)'
complete -c ',sem' -n __fish_sem_needs_command -f -a setup -d 'Replace `git diff` with `sem diff` globally'
complete -c ',sem' -n __fish_sem_needs_command -f -a unsetup -d 'Restore default `git diff` behavior'
complete -c ',sem' -n __fish_sem_needs_command -f -a login -d 'Log in to sem cloud'
complete -c ',sem' -n __fish_sem_needs_command -f -a logout -d 'Log out of sem cloud'
complete -c ',sem' -n __fish_sem_needs_command -f -a whoami -d 'Show current sem cloud identity'
complete -c ',sem' -n __fish_sem_needs_command -f -a cloud -d 'Manage cloud acceleration for a repo (off until you enable it)'
complete -c ',sem' -n __fish_sem_needs_command -f -a review -d 'Attach an agent to a sem-cloud code review'
complete -c ',sem' -n __fish_sem_needs_command -f -a telemetry -d 'Control anonymous usage telemetry (local by default — nothing uploaded)'
complete -c ',sem' -n __fish_sem_needs_command -f -a xref -d 'Show cross-repo dependencies across your indexed repos (requires sem login)'
complete -c ',sem' -n __fish_sem_needs_command -f -a repos -d 'Show where your code is stored: repos indexed on your cloud account and local entity caches'
complete -c ',sem' -n __fish_sem_needs_command -f -a update -d 'Update sem to the latest released version'
complete -c ',sem' -n __fish_sem_needs_command -f -a completions -d 'Generate shell completions'
complete -c ',sem' -n __fish_sem_needs_command -f -a __telemetry-flush -d 'Flush spooled telemetry (internal; spawned in the background)'
complete -c ',sem' -n __fish_sem_needs_command -f -a __update-check -d 'Refresh the cached latest-version info (internal; spawned in the background)'
complete -c ',sem' -n __fish_sem_needs_command -f -a help -d 'Print this message or the help of the given subcommand(s)'
complete -c ',sem' -n "__fish_sem_using_subcommand diff" -l label -d 'Display path label for direct file comparison' -r
complete -c ',sem' -n "__fish_sem_using_subcommand diff" -l commit -d 'Show changes from a specific commit' -r
complete -c ',sem' -n "__fish_sem_using_subcommand diff" -l from -d 'Start of commit range' -r
complete -c ',sem' -n "__fish_sem_using_subcommand diff" -l to -d 'End of commit range' -r
complete -c ',sem' -n "__fish_sem_using_subcommand diff" -l format -d 'Output format' -r -f -a "terminal\t''
plain\t''
json\t''
markdown\t''"
complete -c ',sem' -n "__fish_sem_using_subcommand diff" -l file-exts -d 'Only include files with these extensions (e.g. --file-exts .py .rs)' -r
complete -c ',sem' -n "__fish_sem_using_subcommand diff" -l color -d 'When to use colors' -r -f -a "always\t''
auto\t''
never\t''"
complete -c ',sem' -n "__fish_sem_using_subcommand diff" -s C -l cwd -d 'Run as if started in this directory (like git -C)' -r
complete -c ',sem' -n "__fish_sem_using_subcommand diff" -l staged -d 'Show only staged changes (alias: --cached)'
complete -c ',sem' -n "__fish_sem_using_subcommand diff" -l cached -d 'Show only staged changes (alias for --staged)'
complete -c ',sem' -n "__fish_sem_using_subcommand diff" -l stdin -d 'Read FileChange[] JSON from stdin instead of git'
complete -c ',sem' -n "__fish_sem_using_subcommand diff" -l patch -d 'Read unified diff from stdin (e.g. git diff | sem diff --patch)'
complete -c ',sem' -n "__fish_sem_using_subcommand diff" -l json -d 'Shorthand for --format json'
complete -c ',sem' -n "__fish_sem_using_subcommand diff" -s v -l verbose -d 'Show inline content diffs for each entity'
complete -c ',sem' -n "__fish_sem_using_subcommand diff" -l profile -d 'Show internal timing profile'
complete -c ',sem' -n "__fish_sem_using_subcommand diff" -l no-cosmetics -d 'Hide cosmetic changes (formatting, whitespace, comments only)'
complete -c ',sem' -n "__fish_sem_using_subcommand diff" -s h -l help -d 'Print help (see more with \'--help\')'
complete -c ',sem' -n "__fish_sem_using_subcommand impact" -l entity-id -d 'Look up entity by its ID (from sem diff --format json output)' -r
complete -c ',sem' -n "__fish_sem_using_subcommand impact" -l file -d 'File containing the entity (disambiguates if multiple matches)' -r
complete -c ',sem' -n "__fish_sem_using_subcommand impact" -l format -d 'Output format' -r -f -a "terminal\t''
json\t''"
complete -c ',sem' -n "__fish_sem_using_subcommand impact" -l file-exts -d 'Only include files with these extensions (e.g. --file-exts .py .rs)' -r
complete -c ',sem' -n "__fish_sem_using_subcommand impact" -l depth -d 'Max traversal depth for transitive impact (default 2, 0 = unlimited)' -r
complete -c ',sem' -n "__fish_sem_using_subcommand impact" -l deps -d 'Show direct dependencies only'
complete -c ',sem' -n "__fish_sem_using_subcommand impact" -l dependents -d 'Show direct dependents only'
complete -c ',sem' -n "__fish_sem_using_subcommand impact" -l tests -d 'Show affected test entities only'
complete -c ',sem' -n "__fish_sem_using_subcommand impact" -l json -d 'Output as JSON (shorthand for --format json)'
complete -c ',sem' -n "__fish_sem_using_subcommand impact" -l no-cache -d 'Skip the SQLite entity cache (rebuild from scratch)'
complete -c ',sem' -n "__fish_sem_using_subcommand impact" -l no-default-excludes -d 'Include files and directories excluded by default (generated, fixtures, vendor, benchmarks)'
complete -c ',sem' -n "__fish_sem_using_subcommand impact" -s h -l help -d 'Print help'
complete -c ',sem' -n "__fish_sem_using_subcommand find" -l file -d 'Restrict to entities defined in this file' -r
complete -c ',sem' -n "__fish_sem_using_subcommand find" -l json -d 'Output as JSON'
complete -c ',sem' -n "__fish_sem_using_subcommand find" -s h -l help -d 'Print help'
complete -c ',sem' -n "__fish_sem_using_subcommand callers" -l file -d 'Disambiguate by defining file' -r
complete -c ',sem' -n "__fish_sem_using_subcommand callers" -l limit -d 'Show at most this many callers (all by default)' -r
complete -c ',sem' -n "__fish_sem_using_subcommand callers" -l json -d 'Output as JSON'
complete -c ',sem' -n "__fish_sem_using_subcommand callers" -s h -l help -d 'Print help'
complete -c ',sem' -n "__fish_sem_using_subcommand refs" -l file -d 'Disambiguate by defining file' -r
complete -c ',sem' -n "__fish_sem_using_subcommand refs" -l json -d 'Output as JSON'
complete -c ',sem' -n "__fish_sem_using_subcommand refs" -s h -l help -d 'Print help'
complete -c ',sem' -n "__fish_sem_using_subcommand grep" -s e -l regexp -d 'Pattern to search for, repeatable (rg-style `-e p1 -e p2`); each pattern\'s hits are reported separately rather than merged' -r
complete -c ',sem' -n "__fish_sem_using_subcommand grep" -s i -l ignore-case -d 'Case-insensitive match (disables the trigram prefilter)'
complete -c ',sem' -n "__fish_sem_using_subcommand grep" -l json -d 'Output as JSON (one object: hits, candidate_files, total_files, origin)'
complete -c ',sem' -n "__fish_sem_using_subcommand grep" -s h -l help -d 'Print help'
complete -c ',sem' -n "__fish_sem_using_subcommand graph" -l format -d 'Output format' -r -f -a "terminal\t''
json\t''"
complete -c ',sem' -n "__fish_sem_using_subcommand graph" -l file-exts -d 'Only include files with these extensions (e.g. --file-exts .py .rs)' -r
complete -c ',sem' -n "__fish_sem_using_subcommand graph" -l json -d 'Output as JSON (shorthand for --format json)'
complete -c ',sem' -n "__fish_sem_using_subcommand graph" -l no-cache -d 'Skip the SQLite entity cache (rebuild from scratch)'
complete -c ',sem' -n "__fish_sem_using_subcommand graph" -l no-default-excludes -d 'Include files and directories excluded by default (generated, fixtures, vendor, benchmarks)'
complete -c ',sem' -n "__fish_sem_using_subcommand graph" -s h -l help -d 'Print help'
complete -c ',sem' -n "__fish_sem_using_subcommand blame" -l format -d 'Output format' -r -f -a "terminal\t''
json\t''"
complete -c ',sem' -n "__fish_sem_using_subcommand blame" -l json -d 'Output as JSON (shorthand for --format json)'
complete -c ',sem' -n "__fish_sem_using_subcommand blame" -s h -l help -d 'Print help'
complete -c ',sem' -n "__fish_sem_using_subcommand hook" -s h -l help -d 'Print help'
complete -c ',sem' -n "__fish_sem_using_subcommand log" -l file -d 'File containing the entity (auto-detected if omitted)' -r
complete -c ',sem' -n "__fish_sem_using_subcommand log" -l limit -d 'Maximum number of commits to scan (0 = unlimited)' -r
complete -c ',sem' -n "__fish_sem_using_subcommand log" -l format -d 'Output format' -r -f -a "terminal\t''
json\t''"
complete -c ',sem' -n "__fish_sem_using_subcommand log" -l json -d 'Output as JSON (shorthand for --format json)'
complete -c ',sem' -n "__fish_sem_using_subcommand log" -s v -l verbose -d 'Show content diff between versions'
complete -c ',sem' -n "__fish_sem_using_subcommand log" -s h -l help -d 'Print help'
complete -c ',sem' -n "__fish_sem_using_subcommand entities" -l format -d 'Output format' -r -f -a "terminal\t''
json\t''"
complete -c ',sem' -n "__fish_sem_using_subcommand entities" -l file-exts -d 'Only include files with these extensions (e.g. --file-exts .ts .tsx)' -r
complete -c ',sem' -n "__fish_sem_using_subcommand entities" -l only -d 'List only entities of these kinds (repeatable), e.g. --only function --only struct. Kinds are language-dependent; an unknown kind reports the kinds found' -r
complete -c ',sem' -n "__fish_sem_using_subcommand entities" -l except -d 'List all entities except these kinds (repeatable), e.g. --except import. Cannot be combined with --only' -r
complete -c ',sem' -n "__fish_sem_using_subcommand entities" -l text -d 'Search entity bodies for an exact substring instead of listing: hits come back entity-addressed (file, innermost entity, line, matched text). Use instead of grep for strings in code' -r
complete -c ',sem' -n "__fish_sem_using_subcommand entities" -l json -d 'Output as JSON (shorthand for --format json)'
complete -c ',sem' -n "__fish_sem_using_subcommand entities" -l no-default-excludes -d 'Include files and directories excluded by default (generated, fixtures, vendor, benchmarks)'
complete -c ',sem' -n "__fish_sem_using_subcommand entities" -l signatures -d 'Show each entity\'s header under its row: the signature up to the body plus the first doc-comment line — more than a name, far less than a body'
complete -c ',sem' -n "__fish_sem_using_subcommand entities" -s h -l help -d 'Print help'
complete -c ',sem' -n "__fish_sem_using_subcommand context" -l entity -d 'Entity name, repeatable (--entity A --entity B) to pack context for several entities in one invocation under one --budget; each name resolves (and refuses on ambiguity) exactly like the single-entity form' -r
complete -c ',sem' -n "__fish_sem_using_subcommand context" -l entity-id -d 'Look up entity by its ID (from sem diff --format json output)' -r
complete -c ',sem' -n "__fish_sem_using_subcommand context" -l file -d 'File containing the entity (disambiguates if multiple matches)' -r
complete -c ',sem' -n "__fish_sem_using_subcommand context" -l budget -d 'Token budget' -r
complete -c ',sem' -n "__fish_sem_using_subcommand context" -l hops -d 'Bound related entities to this many graph hops from the target (0 = unbounded)' -r
complete -c ',sem' -n "__fish_sem_using_subcommand context" -l format -d 'Output format' -r -f -a "terminal\t''
json\t''"
complete -c ',sem' -n "__fish_sem_using_subcommand context" -l file-exts -d 'Only include files with these extensions (e.g. --file-exts .py .rs)' -r
complete -c ',sem' -n "__fish_sem_using_subcommand context" -l json -d 'Output as JSON (shorthand for --format json)'
complete -c ',sem' -n "__fish_sem_using_subcommand context" -l no-cache -d 'Skip the SQLite entity cache (rebuild from scratch)'
complete -c ',sem' -n "__fish_sem_using_subcommand context" -l no-default-excludes -d 'Include files and directories excluded by default (generated, fixtures, vendor, benchmarks)'
complete -c ',sem' -n "__fish_sem_using_subcommand context" -l headers -d 'Render each packed entity as its header (signature plus first doc-comment line) instead of its body — the same budget buys a much wider map'
complete -c ',sem' -n "__fish_sem_using_subcommand context" -s h -l help -d 'Print help'
complete -c ',sem' -n "__fish_sem_using_subcommand stats" -s h -l help -d 'Print help'
complete -c ',sem' -n "__fish_sem_using_subcommand mcp" -l resident -d 'Removed: used to spawn the per-repo sidecar socket. The mmap query index answers cold in 6-7ms, deleting the sidecar\'s reason to exist. Kept as a backward-compatible no-op (exits immediately, does nothing) so an existing `sem setup` SessionStart hook that still invokes `sem mcp --resident` doesn\'t error'
complete -c ',sem' -n "__fish_sem_using_subcommand mcp" -s h -l help -d 'Print help'
complete -c ',sem' -n "__fish_sem_using_subcommand setup" -s h -l help -d 'Print help'
complete -c ',sem' -n "__fish_sem_using_subcommand unsetup" -s h -l help -d 'Print help'
complete -c ',sem' -n "__fish_sem_using_subcommand login" -l endpoint -d 'API endpoint' -r
complete -c ',sem' -n "__fish_sem_using_subcommand login" -s h -l help -d 'Print help'
complete -c ',sem' -n "__fish_sem_using_subcommand logout" -s h -l help -d 'Print help'
complete -c ',sem' -n "__fish_sem_using_subcommand whoami" -s h -l help -d 'Print help'
complete -c ',sem' -n "__fish_sem_using_subcommand cloud; and not __fish_seen_subcommand_from enable share list status preview log never forget help" -s h -l help -d 'Print help'
complete -c ',sem' -n "__fish_sem_using_subcommand cloud; and not __fish_seen_subcommand_from enable share list status preview log never forget help" -f -a enable -d 'Enable cloud queries for this public repo (shows what\'s sent, asks first)'
complete -c ',sem' -n "__fish_sem_using_subcommand cloud; and not __fish_seen_subcommand_from enable share list status preview log never forget help" -f -a share -d 'Share this private repo\'s index with the cloud (extra confirmation)'
complete -c ',sem' -n "__fish_sem_using_subcommand cloud; and not __fish_seen_subcommand_from enable share list status preview log never forget help" -f -a list -d 'List every repo indexed under your account'
complete -c ',sem' -n "__fish_sem_using_subcommand cloud; and not __fish_seen_subcommand_from enable share list status preview log never forget help" -f -a status -d 'Show cloud + telemetry state for this repo (offline; sends nothing)'
complete -c ',sem' -n "__fish_sem_using_subcommand cloud; and not __fish_seen_subcommand_from enable share list status preview log never forget help" -f -a preview -d 'Print the exact request a cloud query would send'
complete -c ',sem' -n "__fish_sem_using_subcommand cloud; and not __fish_seen_subcommand_from enable share list status preview log never forget help" -f -a log -d 'Print the local ledger of every outbound cloud request'
complete -c ',sem' -n "__fish_sem_using_subcommand cloud; and not __fish_seen_subcommand_from enable share list status preview log never forget help" -f -a never -d 'Stop offering cloud for this repo (or suppress the tip globally)'
complete -c ',sem' -n "__fish_sem_using_subcommand cloud; and not __fish_seen_subcommand_from enable share list status preview log never forget help" -f -a forget -d 'Delete this repo\'s cloud index and unregister it'
complete -c ',sem' -n "__fish_sem_using_subcommand cloud; and not __fish_seen_subcommand_from enable share list status preview log never forget help" -f -a help -d 'Print this message or the help of the given subcommand(s)'
complete -c ',sem' -n "__fish_sem_using_subcommand cloud; and __fish_seen_subcommand_from enable" -s h -l help -d 'Print help'
complete -c ',sem' -n "__fish_sem_using_subcommand cloud; and __fish_seen_subcommand_from share" -s h -l help -d 'Print help'
complete -c ',sem' -n "__fish_sem_using_subcommand cloud; and __fish_seen_subcommand_from list" -s h -l help -d 'Print help'
complete -c ',sem' -n "__fish_sem_using_subcommand cloud; and __fish_seen_subcommand_from status" -s h -l help -d 'Print help'
complete -c ',sem' -n "__fish_sem_using_subcommand cloud; and __fish_seen_subcommand_from preview" -s h -l help -d 'Print help'
complete -c ',sem' -n "__fish_sem_using_subcommand cloud; and __fish_seen_subcommand_from log" -s h -l help -d 'Print help'
complete -c ',sem' -n "__fish_sem_using_subcommand cloud; and __fish_seen_subcommand_from never" -s h -l help -d 'Print help'
complete -c ',sem' -n "__fish_sem_using_subcommand cloud; and __fish_seen_subcommand_from forget" -s h -l help -d 'Print help'
complete -c ',sem' -n "__fish_sem_using_subcommand cloud; and __fish_seen_subcommand_from help" -f -a enable -d 'Enable cloud queries for this public repo (shows what\'s sent, asks first)'
complete -c ',sem' -n "__fish_sem_using_subcommand cloud; and __fish_seen_subcommand_from help" -f -a share -d 'Share this private repo\'s index with the cloud (extra confirmation)'
complete -c ',sem' -n "__fish_sem_using_subcommand cloud; and __fish_seen_subcommand_from help" -f -a list -d 'List every repo indexed under your account'
complete -c ',sem' -n "__fish_sem_using_subcommand cloud; and __fish_seen_subcommand_from help" -f -a status -d 'Show cloud + telemetry state for this repo (offline; sends nothing)'
complete -c ',sem' -n "__fish_sem_using_subcommand cloud; and __fish_seen_subcommand_from help" -f -a preview -d 'Print the exact request a cloud query would send'
complete -c ',sem' -n "__fish_sem_using_subcommand cloud; and __fish_seen_subcommand_from help" -f -a log -d 'Print the local ledger of every outbound cloud request'
complete -c ',sem' -n "__fish_sem_using_subcommand cloud; and __fish_seen_subcommand_from help" -f -a never -d 'Stop offering cloud for this repo (or suppress the tip globally)'
complete -c ',sem' -n "__fish_sem_using_subcommand cloud; and __fish_seen_subcommand_from help" -f -a forget -d 'Delete this repo\'s cloud index and unregister it'
complete -c ',sem' -n "__fish_sem_using_subcommand cloud; and __fish_seen_subcommand_from help" -f -a help -d 'Print this message or the help of the given subcommand(s)'
complete -c ',sem' -n "__fish_sem_using_subcommand review; and not __fish_seen_subcommand_from listen help" -s h -l help -d 'Print help'
complete -c ',sem' -n "__fish_sem_using_subcommand review; and not __fish_seen_subcommand_from listen help" -f -a listen -d 'Join a sem-cloud code review as a live listener (the one-command agent attach)'
complete -c ',sem' -n "__fish_sem_using_subcommand review; and not __fish_seen_subcommand_from listen help" -f -a help -d 'Print this message or the help of the given subcommand(s)'
complete -c ',sem' -n "__fish_sem_using_subcommand review; and __fish_seen_subcommand_from listen" -l dry-run -d 'Print the assembled command and environment (secrets masked) instead of launching'
complete -c ',sem' -n "__fish_sem_using_subcommand review; and __fish_seen_subcommand_from listen" -s h -l help -d 'Print help (see more with \'--help\')'
complete -c ',sem' -n "__fish_sem_using_subcommand review; and __fish_seen_subcommand_from help" -f -a listen -d 'Join a sem-cloud code review as a live listener (the one-command agent attach)'
complete -c ',sem' -n "__fish_sem_using_subcommand review; and __fish_seen_subcommand_from help" -f -a help -d 'Print this message or the help of the given subcommand(s)'
complete -c ',sem' -n "__fish_sem_using_subcommand telemetry; and not __fish_seen_subcommand_from on local off preview help" -s h -l help -d 'Print help'
complete -c ',sem' -n "__fish_sem_using_subcommand telemetry; and not __fish_seen_subcommand_from on local off preview help" -f -a on -d 'Record usage locally and upload it to help improve sem'
complete -c ',sem' -n "__fish_sem_using_subcommand telemetry; and not __fish_seen_subcommand_from on local off preview help" -f -a local -d 'Record usage locally only; never upload (the default)'
complete -c ',sem' -n "__fish_sem_using_subcommand telemetry; and not __fish_seen_subcommand_from on local off preview help" -f -a off -d 'Record nothing'
complete -c ',sem' -n "__fish_sem_using_subcommand telemetry; and not __fish_seen_subcommand_from on local off preview help" -f -a preview -d 'Show the current mode and what would be sent'
complete -c ',sem' -n "__fish_sem_using_subcommand telemetry; and not __fish_seen_subcommand_from on local off preview help" -f -a help -d 'Print this message or the help of the given subcommand(s)'
complete -c ',sem' -n "__fish_sem_using_subcommand telemetry; and __fish_seen_subcommand_from on" -s h -l help -d 'Print help'
complete -c ',sem' -n "__fish_sem_using_subcommand telemetry; and __fish_seen_subcommand_from local" -s h -l help -d 'Print help'
complete -c ',sem' -n "__fish_sem_using_subcommand telemetry; and __fish_seen_subcommand_from off" -s h -l help -d 'Print help'
complete -c ',sem' -n "__fish_sem_using_subcommand telemetry; and __fish_seen_subcommand_from preview" -s h -l help -d 'Print help'
complete -c ',sem' -n "__fish_sem_using_subcommand telemetry; and __fish_seen_subcommand_from help" -f -a on -d 'Record usage locally and upload it to help improve sem'
complete -c ',sem' -n "__fish_sem_using_subcommand telemetry; and __fish_seen_subcommand_from help" -f -a local -d 'Record usage locally only; never upload (the default)'
complete -c ',sem' -n "__fish_sem_using_subcommand telemetry; and __fish_seen_subcommand_from help" -f -a off -d 'Record nothing'
complete -c ',sem' -n "__fish_sem_using_subcommand telemetry; and __fish_seen_subcommand_from help" -f -a preview -d 'Show the current mode and what would be sent'
complete -c ',sem' -n "__fish_sem_using_subcommand telemetry; and __fish_seen_subcommand_from help" -f -a help -d 'Print this message or the help of the given subcommand(s)'
complete -c ',sem' -n "__fish_sem_using_subcommand xref" -l json -d 'JSON output'
complete -c ',sem' -n "__fish_sem_using_subcommand xref" -s h -l help -d 'Print help'
complete -c ',sem' -n "__fish_sem_using_subcommand repos" -l json -d 'JSON output'
complete -c ',sem' -n "__fish_sem_using_subcommand repos" -s h -l help -d 'Print help'
complete -c ',sem' -n "__fish_sem_using_subcommand update" -s h -l help -d 'Print help'
complete -c ',sem' -n "__fish_sem_using_subcommand completions" -s h -l help -d 'Print help'
complete -c ',sem' -n "__fish_sem_using_subcommand __telemetry-flush" -s h -l help -d 'Print help'
complete -c ',sem' -n "__fish_sem_using_subcommand __update-check" -s h -l help -d 'Print help'
complete -c ',sem' -n "__fish_sem_using_subcommand help; and not __fish_seen_subcommand_from diff impact find callers refs grep graph blame hook log entities context stats mcp setup unsetup login logout whoami cloud review telemetry xref repos update completions __telemetry-flush __update-check help" -f -a diff -d 'Show semantic diff of changes (supports git diff syntax). Untracked files are excluded, matching git behavior'
complete -c ',sem' -n "__fish_sem_using_subcommand help; and not __fish_seen_subcommand_from diff impact find callers refs grep graph blame hook log entities context stats mcp setup unsetup login logout whoami cloud review telemetry xref repos update completions __telemetry-flush __update-check help" -f -a impact -d 'Show impact of changing an entity (deps, dependents, transitive impact, tests)'
complete -c ',sem' -n "__fish_sem_using_subcommand help; and not __fish_seen_subcommand_from diff impact find callers refs grep graph blame hook log entities context stats mcp setup unsetup login logout whoami cloud review telemetry xref repos update completions __telemetry-flush __update-check help" -f -a find -d 'Find entity definitions by name — answers from the mmap query index when one exists (cold-process, <10ms on a large repo); falls back to a fresh build otherwise, which then leaves an index for next time'
complete -c ',sem' -n "__fish_sem_using_subcommand help; and not __fish_seen_subcommand_from diff impact find callers refs grep graph blame hook log entities context stats mcp setup unsetup login logout whoami cloud review telemetry xref repos update completions __telemetry-flush __update-check help" -f -a callers -d 'Show direct callers of an entity (who calls/references it) — the index\'s reverse postings, same freshness/fallback discipline as `find`'
complete -c ',sem' -n "__fish_sem_using_subcommand help; and not __fish_seen_subcommand_from diff impact find callers refs grep graph blame hook log entities context stats mcp setup unsetup login logout whoami cloud review telemetry xref repos update completions __telemetry-flush __update-check help" -f -a refs -d 'Show direct refs of an entity (what it calls/references) — the index\'s forward postings, same freshness/fallback discipline as `find`'
complete -c ',sem' -n "__fish_sem_using_subcommand help; and not __fish_seen_subcommand_from diff impact find callers refs grep graph blame hook log entities context stats mcp setup unsetup login logout whoami cloud review telemetry xref repos update completions __telemetry-flush __update-check help" -f -a grep -d 'Search file text — rg-compatible `file:line:text` output, served from the mmap query index\'s trigram postings when one exists (cold process, target <50ms on a large repo); falls back to a plain scan otherwise. Pattern is always a regex (same default as rg without `-F`); patterns with no usable trigram (e.g. `-i`, short literals, unconstrained alternation) degrade to an honest full scan rather than a wrong answer'
complete -c ',sem' -n "__fish_sem_using_subcommand help; and not __fish_seen_subcommand_from diff impact find callers refs grep graph blame hook log entities context stats mcp setup unsetup login logout whoami cloud review telemetry xref repos update completions __telemetry-flush __update-check help" -f -a graph -d 'Show the full entity dependency graph'
complete -c ',sem' -n "__fish_sem_using_subcommand help; and not __fish_seen_subcommand_from diff impact find callers refs grep graph blame hook log entities context stats mcp setup unsetup login logout whoami cloud review telemetry xref repos update completions __telemetry-flush __update-check help" -f -a blame -d 'Show semantic blame — who last modified each entity'
complete -c ',sem' -n "__fish_sem_using_subcommand help; and not __fish_seen_subcommand_from diff impact find callers refs grep graph blame hook log entities context stats mcp setup unsetup login logout whoami cloud review telemetry xref repos update completions __telemetry-flush __update-check help" -f -a hook -d 'Internal plumbing for agent-harness hooks (hidden)'
complete -c ',sem' -n "__fish_sem_using_subcommand help; and not __fish_seen_subcommand_from diff impact find callers refs grep graph blame hook log entities context stats mcp setup unsetup login logout whoami cloud review telemetry xref repos update completions __telemetry-flush __update-check help" -f -a log -d 'Show evolution of an entity through git history, or, with no entity, the repo\'s history analytics: hotspots and co-change pairs'
complete -c ',sem' -n "__fish_sem_using_subcommand help; and not __fish_seen_subcommand_from diff impact find callers refs grep graph blame hook log entities context stats mcp setup unsetup login logout whoami cloud review telemetry xref repos update completions __telemetry-flush __update-check help" -f -a entities -d 'List entities under one or more file or directory paths'
complete -c ',sem' -n "__fish_sem_using_subcommand help; and not __fish_seen_subcommand_from diff impact find callers refs grep graph blame hook log entities context stats mcp setup unsetup login logout whoami cloud review telemetry xref repos update completions __telemetry-flush __update-check help" -f -a context -d 'Show token-budgeted context for an entity'
complete -c ',sem' -n "__fish_sem_using_subcommand help; and not __fish_seen_subcommand_from diff impact find callers refs grep graph blame hook log entities context stats mcp setup unsetup login logout whoami cloud review telemetry xref repos update completions __telemetry-flush __update-check help" -f -a stats -d 'Show lifetime diff statistics'
complete -c ',sem' -n "__fish_sem_using_subcommand help; and not __fish_seen_subcommand_from diff impact find callers refs grep graph blame hook log entities context stats mcp setup unsetup login logout whoami cloud review telemetry xref repos update completions __telemetry-flush __update-check help" -f -a mcp -d 'Start the MCP server (stdin/stdout transport)'
complete -c ',sem' -n "__fish_sem_using_subcommand help; and not __fish_seen_subcommand_from diff impact find callers refs grep graph blame hook log entities context stats mcp setup unsetup login logout whoami cloud review telemetry xref repos update completions __telemetry-flush __update-check help" -f -a setup -d 'Replace `git diff` with `sem diff` globally'
complete -c ',sem' -n "__fish_sem_using_subcommand help; and not __fish_seen_subcommand_from diff impact find callers refs grep graph blame hook log entities context stats mcp setup unsetup login logout whoami cloud review telemetry xref repos update completions __telemetry-flush __update-check help" -f -a unsetup -d 'Restore default `git diff` behavior'
complete -c ',sem' -n "__fish_sem_using_subcommand help; and not __fish_seen_subcommand_from diff impact find callers refs grep graph blame hook log entities context stats mcp setup unsetup login logout whoami cloud review telemetry xref repos update completions __telemetry-flush __update-check help" -f -a login -d 'Log in to sem cloud'
complete -c ',sem' -n "__fish_sem_using_subcommand help; and not __fish_seen_subcommand_from diff impact find callers refs grep graph blame hook log entities context stats mcp setup unsetup login logout whoami cloud review telemetry xref repos update completions __telemetry-flush __update-check help" -f -a logout -d 'Log out of sem cloud'
complete -c ',sem' -n "__fish_sem_using_subcommand help; and not __fish_seen_subcommand_from diff impact find callers refs grep graph blame hook log entities context stats mcp setup unsetup login logout whoami cloud review telemetry xref repos update completions __telemetry-flush __update-check help" -f -a whoami -d 'Show current sem cloud identity'
complete -c ',sem' -n "__fish_sem_using_subcommand help; and not __fish_seen_subcommand_from diff impact find callers refs grep graph blame hook log entities context stats mcp setup unsetup login logout whoami cloud review telemetry xref repos update completions __telemetry-flush __update-check help" -f -a cloud -d 'Manage cloud acceleration for a repo (off until you enable it)'
complete -c ',sem' -n "__fish_sem_using_subcommand help; and not __fish_seen_subcommand_from diff impact find callers refs grep graph blame hook log entities context stats mcp setup unsetup login logout whoami cloud review telemetry xref repos update completions __telemetry-flush __update-check help" -f -a review -d 'Attach an agent to a sem-cloud code review'
complete -c ',sem' -n "__fish_sem_using_subcommand help; and not __fish_seen_subcommand_from diff impact find callers refs grep graph blame hook log entities context stats mcp setup unsetup login logout whoami cloud review telemetry xref repos update completions __telemetry-flush __update-check help" -f -a telemetry -d 'Control anonymous usage telemetry (local by default — nothing uploaded)'
complete -c ',sem' -n "__fish_sem_using_subcommand help; and not __fish_seen_subcommand_from diff impact find callers refs grep graph blame hook log entities context stats mcp setup unsetup login logout whoami cloud review telemetry xref repos update completions __telemetry-flush __update-check help" -f -a xref -d 'Show cross-repo dependencies across your indexed repos (requires sem login)'
complete -c ',sem' -n "__fish_sem_using_subcommand help; and not __fish_seen_subcommand_from diff impact find callers refs grep graph blame hook log entities context stats mcp setup unsetup login logout whoami cloud review telemetry xref repos update completions __telemetry-flush __update-check help" -f -a repos -d 'Show where your code is stored: repos indexed on your cloud account and local entity caches'
complete -c ',sem' -n "__fish_sem_using_subcommand help; and not __fish_seen_subcommand_from diff impact find callers refs grep graph blame hook log entities context stats mcp setup unsetup login logout whoami cloud review telemetry xref repos update completions __telemetry-flush __update-check help" -f -a update -d 'Update sem to the latest released version'
complete -c ',sem' -n "__fish_sem_using_subcommand help; and not __fish_seen_subcommand_from diff impact find callers refs grep graph blame hook log entities context stats mcp setup unsetup login logout whoami cloud review telemetry xref repos update completions __telemetry-flush __update-check help" -f -a completions -d 'Generate shell completions'
complete -c ',sem' -n "__fish_sem_using_subcommand help; and not __fish_seen_subcommand_from diff impact find callers refs grep graph blame hook log entities context stats mcp setup unsetup login logout whoami cloud review telemetry xref repos update completions __telemetry-flush __update-check help" -f -a __telemetry-flush -d 'Flush spooled telemetry (internal; spawned in the background)'
complete -c ',sem' -n "__fish_sem_using_subcommand help; and not __fish_seen_subcommand_from diff impact find callers refs grep graph blame hook log entities context stats mcp setup unsetup login logout whoami cloud review telemetry xref repos update completions __telemetry-flush __update-check help" -f -a __update-check -d 'Refresh the cached latest-version info (internal; spawned in the background)'
complete -c ',sem' -n "__fish_sem_using_subcommand help; and not __fish_seen_subcommand_from diff impact find callers refs grep graph blame hook log entities context stats mcp setup unsetup login logout whoami cloud review telemetry xref repos update completions __telemetry-flush __update-check help" -f -a help -d 'Print this message or the help of the given subcommand(s)'
complete -c ',sem' -n "__fish_sem_using_subcommand help; and __fish_seen_subcommand_from cloud" -f -a enable -d 'Enable cloud queries for this public repo (shows what\'s sent, asks first)'
complete -c ',sem' -n "__fish_sem_using_subcommand help; and __fish_seen_subcommand_from cloud" -f -a share -d 'Share this private repo\'s index with the cloud (extra confirmation)'
complete -c ',sem' -n "__fish_sem_using_subcommand help; and __fish_seen_subcommand_from cloud" -f -a list -d 'List every repo indexed under your account'
complete -c ',sem' -n "__fish_sem_using_subcommand help; and __fish_seen_subcommand_from cloud" -f -a status -d 'Show cloud + telemetry state for this repo (offline; sends nothing)'
complete -c ',sem' -n "__fish_sem_using_subcommand help; and __fish_seen_subcommand_from cloud" -f -a preview -d 'Print the exact request a cloud query would send'
complete -c ',sem' -n "__fish_sem_using_subcommand help; and __fish_seen_subcommand_from cloud" -f -a log -d 'Print the local ledger of every outbound cloud request'
complete -c ',sem' -n "__fish_sem_using_subcommand help; and __fish_seen_subcommand_from cloud" -f -a never -d 'Stop offering cloud for this repo (or suppress the tip globally)'
complete -c ',sem' -n "__fish_sem_using_subcommand help; and __fish_seen_subcommand_from cloud" -f -a forget -d 'Delete this repo\'s cloud index and unregister it'
complete -c ',sem' -n "__fish_sem_using_subcommand help; and __fish_seen_subcommand_from review" -f -a listen -d 'Join a sem-cloud code review as a live listener (the one-command agent attach)'
complete -c ',sem' -n "__fish_sem_using_subcommand help; and __fish_seen_subcommand_from telemetry" -f -a on -d 'Record usage locally and upload it to help improve sem'
complete -c ',sem' -n "__fish_sem_using_subcommand help; and __fish_seen_subcommand_from telemetry" -f -a local -d 'Record usage locally only; never upload (the default)'
complete -c ',sem' -n "__fish_sem_using_subcommand help; and __fish_seen_subcommand_from telemetry" -f -a off -d 'Record nothing'
complete -c ',sem' -n "__fish_sem_using_subcommand help; and __fish_seen_subcommand_from telemetry" -f -a preview -d 'Show the current mode and what would be sent'
