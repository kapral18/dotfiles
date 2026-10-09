import type { Register } from 'claude-code'

// Throwaway locations never get a map.
const SCRATCH = /^(\/private)?\/(tmp|var\/folders)\//
// Docs-only and test-only edits need no area (k-behavior-map skill).
// Matched against the repo-relative path.
const DOCS_OR_TESTS = /\.(md|mdx|rst)$|(^|\/)(tests?|__tests__|spec)\/|[._-](test|spec)\.[^/]+$|(^|\/)test_[^/]+$/

const parent = (path: string) => path.slice(0, Math.max(path.lastIndexOf('/'), 0)) || '/'

export const register: Register = on => {
  // Directories already stopped once and map items already shown, per repo.
  const seen = new Set<string>()

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

    const items = lines
      .map(line => /^(entry|area) ([^:]+):/.exec(line)?.[2])
      .filter((item): item is string => item !== undefined && !seen.has(`${repo}\0item\0${item}`))
    const ran = await next(e)
    if (items.length === 0 || ran.deny !== undefined || ran.isError === true) return ran
    for (const item of items) seen.add(`${repo}\0item\0${item}`)
    return {
      ...ran,
      context: [
        ...(ran.context ?? []),
        `behavior-map: this edit touches ${items.join(', ')}. ` +
          'Read each with `,behavior-map show <id or area>` and keep those behaviors, or change them on purpose and update the entries (k-behavior-map skill).',
      ],
    }
  }).catch(($, e, next) => next(e))
}
