import type { Register } from 'claude-code'

// Throwaway locations never get a map.
const SCRATCH = /^(\/private)?\/(tmp|var\/folders)\//
// Docs-only and test-only edits need no area (k-behavior-map skill).
// Matched against the repo-relative path.
const DOCS_OR_TESTS = /\.(md|mdx|rst)$|(^|\/)(tests?|__tests__|spec)\/|[._-](test|spec)\.[^/]+$|(^|\/)test_[^/]+$/

const parent = (path: string) => path.slice(0, Math.max(path.lastIndexOf('/'), 0)) || '/'

// A Bash command that may write files: a redirect, an in-place edit, a scripting runtime, a file command, or a git command that writes the working tree.
// Other commands are not checked; a missed write only loses this guard's note.
// Commands that move HEAD (merge, pull, rebase, switch, cherry-pick, am, reset) bring code the agent did not write, so they are left out;
// a branch-switching `git checkout` leaves the files it switched clean, and carried changes keep their change time.
const WRITES =
  /(?:^|[^0-9&<>])>(?!&)|\b(?:sed|perl)\b[^|;&\n]*(?:\s-[a-zA-Z0-9]*i|--in-place)|\b(?:python3?|node|bun|deno|ruby|tee|mv|cp|touch|ln|patch|truncate|dd|chezmoi)\b|\bgit\s+(?:apply|checkout|restore|stash|mv)\b/

// The files `find` lists per call, to stay under the argument limit.
const CHUNK = 200

export const register: Register = on => {
  // Directories already stopped once and map items already shown, per repo.
  const seen = new Set<string>()

  // The note for touched entries and areas not yet shown, from `affected` output lines; marks them shown.
  const touched = (repo: string, lines: readonly string[]) => {
    const items = lines
      .map(line => /^(entry|area) ([^:]+):/.exec(line)?.[2])
      .filter((item): item is string => item !== undefined && !seen.has(`${repo}\0item\0${item}`))
    if (items.length === 0) return undefined
    for (const item of items) seen.add(`${repo}\0item\0${item}`)
    return (
      `behavior-map: this edit touches ${items.join(', ')}. ` +
      'Read each with `,behavior-map show <id or area>` and keep those behaviors, or change them on purpose and update the entries (k-behavior-map skill).'
    )
  }

  // A /clear starts a new session in the same process.
  on('session.end', ($, e, next) => {
    seen.clear()
    return next(e)
  })

  on('tool.call', { tool: ['Edit', 'Write', 'NotebookEdit'] }, async ($, e, next) => {
    const path = 'notebook_path' in e ? e.notebook_path : e.file_path
    if (!path.startsWith('/') || SCRATCH.test(path)) return next(e)

    let dir = parent(path)
    while (dir !== '/' && !(await $.fs.exists(dir))) dir = parent(dir)
    const top = await $.process.run(['git', 'rev-parse', '--show-toplevel'], { cwd: dir })
    if (top.exitCode !== 0) return next(e)
    const repo = top.stdout.trim()
    const relative = path.startsWith(`${repo}/`) ? path.slice(repo.length + 1) : path

    const map = await $.process.run([',behavior-map', 'affected', path], { cwd: dir, timeoutMs: 15000 })
    if (map.exitCode !== 0) return next(e)
    const lines = map.stdout.split('\n')

    const unmapped = lines.find(line => line.startsWith('unmapped: '))?.slice('unmapped: '.length)
    if (unmapped && !DOCS_OR_TESTS.test(relative) && !seen.has(`${repo}\0dir\0${unmapped}`)) {
      seen.add(`${repo}\0dir\0${unmapped}`)
      return {
        deny:
          `${$.plugin.name}: ${unmapped} in ${repo} has no behavior-map area. ` +
          'Map it first: k-behavior-map skill, area init. ' +
          'For a file in the repo root or a shared directory, add it as a file anchor to the closest entry of an existing area instead. ' +
          'Retry without a map only in a throwaway clone; this check stops a directory once per session.',
      }
    }

    const ran = await next(e)
    if (ran.deny !== undefined || ran.isError === true) return ran
    const note = touched(repo, lines)
    return note === undefined ? ran : { ...ran, context: [...(ran.context ?? []), note] }
  }).catch(($, e, next) => next(e))

  // A Bash command cannot be refused before it runs, since its paths are unknown: after it changed code, the guard adds the same notes as context.
  // It sees only the git repo of the session's working directory, and only the main agent's commands.
  on('tool.call', { tool: 'Bash' }, async ($, e, next) => {
    if (e.agentId !== undefined || !WRITES.test(e.command)) return next(e)
    // A marker per call: `mktemp` sets its change time just before the command, and a parallel call cannot move it.
    const made = await $.process.run(['sh', '-c', 'mktemp "${TMPDIR:-/tmp}/behavior-map-guard.XXXXXX"'])
    if (made.exitCode !== 0) return next(e)
    const marker = made.stdout.trim()
    try {
      const ran = await next(e)
      if (ran.deny !== undefined) return ran

      const top = await $.process.run(['git', 'rev-parse', '--show-toplevel'])
      const repo = top.stdout.trim()
      if (top.exitCode !== 0 || SCRATCH.test(`${repo}/`)) return ran
      // Changed, staged, renamed, and untracked paths; a rename's old path follows its new one and is skipped.
      const status = await $.process.run(['git', '--no-optional-locks', 'status', '--porcelain=v1', '-z', '--untracked-files=all'], { cwd: repo, timeoutMs: 15000 })
      if (status.exitCode !== 0) return ran
      const tokens = status.stdout.split('\0')
      const dirty: string[] = []
      for (let i = 0; i < tokens.length; i++) {
        const entry = tokens[i] ?? ''
        if (entry.length < 4) continue
        dirty.push(entry.slice(3))
        // A rename shows R in the index column, or in the worktree column for an intent-to-add file.
        if ('RC'.includes(entry[0] ?? ' ') || 'RC'.includes(entry[1] ?? ' ')) i++
      }
      // The change time, not the content time: `mv` and `cp -p` keep a file's mtime. A `./` prefix keeps a name like `-x` from reading as an option.
      // `find` fails on a deleted path but still lists the rest, so its exit code is ignored.
      const files: string[] = []
      for (let i = 0; i < dirty.length; i += CHUNK) {
        const found = await $.process.run(['find', ...dirty.slice(i, i + CHUNK).map(path => `./${path}`), '-maxdepth', '0', '-cnewer', marker, '-print'], { cwd: repo, timeoutMs: 15000 })
        files.push(...found.stdout.split('\n').filter(line => line !== '').map(line => line.slice(2)))
      }
      if (files.length === 0) return ran
      const map = await $.process.run([',behavior-map', 'affected', ...files], { cwd: repo, timeoutMs: 15000 })
      if (map.exitCode !== 0) return ran
      const lines = map.stdout.split('\n')

      const notes: string[] = []
      // Docs-only and test-only files need no area, so a directory counts only for a changed code file in it.
      const codeDirs = new Set(files.filter(file => !DOCS_OR_TESTS.test(file)).map(file => (file.includes('/') ? file.slice(0, file.lastIndexOf('/')) : '.')))
      const unmapped = (lines.find(line => line.startsWith('unmapped: '))?.slice('unmapped: '.length).split(', ') ?? []).filter(
        dir => codeDirs.has(dir) && !seen.has(`${repo}\0noted\0${dir}`),
      )
      // Its own key: a note does not use up the Edit refusal for the same directory.
      if (unmapped.length > 0) {
        for (const dir of unmapped) seen.add(`${repo}\0noted\0${dir}`)
        notes.push(
          `${$.plugin.name}: this command changed code in ${unmapped.join(', ')} in ${repo}, which has no behavior-map area. ` +
            'Map it now: k-behavior-map skill, area init. ' +
            'For a file in the repo root or a shared directory, add it as a file anchor to the closest entry of an existing area instead.',
        )
      }
      const note = touched(repo, lines)
      if (note !== undefined) notes.push(note)
      return notes.length === 0 ? ran : { ...ran, context: [...(ran.context ?? []), ...notes] }
    } finally {
      await $.process.run(['rm', '-f', marker]).catch(() => undefined)
    }
  }).catch(($, e, next) => next(e))
}
