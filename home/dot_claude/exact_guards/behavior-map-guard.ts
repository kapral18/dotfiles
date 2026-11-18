import { existsSync, mkdirSync, rmSync, writeFileSync } from 'node:fs'
import { homedir } from 'node:os'
import { join } from 'node:path'

import { claimOnce, context, deny, type HookInput, type HookOutput, logFire, run, safe, sessionPath, stateDir } from './hook'

const GUARD = 'behavior-map-guard'
// Throwaway locations never get a map.
const SCRATCH = /^(\/private)?\/(tmp|var\/folders)\//
// Docs-only and test-only edits need no area (k-behavior-map skill).
// Matched against the repo-relative path.
const DOCS_OR_TESTS = /\.(md|mdx|rst)$|(^|\/)(tests?|__tests__|spec)\/|[._-](test|spec)\.[^/]+$|(^|\/)test_[^/]+$/

// A Bash command that may write files: a redirect, an in-place edit, a scripting runtime, a file command, or a git command that writes the working tree.
// Other commands are not checked; a missed write only loses this guard's note.
// Commands that move HEAD (merge, pull, rebase, switch, cherry-pick, am, reset) bring code the agent did not write, so they are left out;
// a branch-switching `git checkout` leaves the files it switched clean, and carried changes keep their change time.
const WRITES =
  /(?:^|[^0-9&<>])>(?!&)|\b(?:sed|perl)\b[^|;&\n]*(?:\s-[a-zA-Z0-9]*i|--in-place)|\b(?:python3?|node|bun|deno|ruby|tee|mv|cp|touch|ln|patch|truncate|dd|chezmoi)\b|\bgit\s+(?:apply|checkout|restore|stash|mv)\b/

// The files `find` lists per call, to stay under the argument limit.
const CHUNK = 200

const BEHAVIOR_MAP = join(homedir(), 'bin', ',behavior-map')
const parent = (path: string) => path.slice(0, Math.max(path.lastIndexOf('/'), 0)) || '/'

const unmappedDirs = (lines: readonly string[]) => lines.find(line => line.startsWith('unmapped: '))?.slice('unmapped: '.length).split(', ') ?? []

// The note for touched entries and areas not yet shown, from `affected` output lines; marks them shown.
const touched = (session: string, repo: string, lines: readonly string[]) => {
  const items = lines
    .map(line => /^(entry|area) ([^:]+):/.exec(line)?.[2])
    .filter((item): item is string => item !== undefined && claimOnce(GUARD, session, `${repo}\0item\0${item}`))
  if (items.length === 0) return undefined
  return (
    `behavior-map: this edit touches ${items.join(', ')}. ` +
    'Read each with `,behavior-map show <id or area>` and keep those behaviors, or change them on purpose and update the entries (k-behavior-map skill).'
  )
}

type Located = { repo: string; relative: string; lines: string[] }

const locate = (path: string): Located | undefined => {
  let dir = parent(path)
  while (dir !== '/' && !existsSync(dir)) dir = parent(dir)
  const top = run(['git', 'rev-parse', '--show-toplevel'], { cwd: dir })
  if (top.exitCode !== 0) return undefined
  const repo = top.stdout.trim()
  const map = run([BEHAVIOR_MAP, 'affected', path], { cwd: dir })
  if (map.exitCode !== 0) return undefined
  return { repo, relative: path.startsWith(`${repo}/`) ? path.slice(repo.length + 1) : path, lines: map.stdout.split('\n') }
}

// Before an edit: an unmapped code directory is stopped once per session.
const beforeEdit = (input: HookInput, path: string): HookOutput => {
  const found = locate(path)
  if (!found) return undefined
  const { repo, relative, lines } = found
  // A path through a symlink can list two directories; each is keyed alone, as on the Bash path.
  const unmapped = DOCS_OR_TESTS.test(relative) ? [] : unmappedDirs(lines).filter(dir => claimOnce(GUARD, input.session_id, `${repo}\0dir\0${dir}`))
  if (unmapped.length === 0) return undefined
  logFire(input, 'behavior-map-guard:unmapped-edit', relative)
  return deny(
    `${GUARD}: ${unmapped.join(', ')} in ${repo} has no behavior-map area. ` +
      'Map it first: k-behavior-map skill, area init. ' +
      'For a file in the repo root or a shared directory, add it as a file anchor to the closest entry of an existing area instead; with no area yet, map the subsystem it serves first. ' +
      'Retry without a map only in a throwaway clone; this check stops a directory once per session.',
  )
}

// After an edit: the entries it touched, each shown once per session.
const afterEdit = (input: HookInput, path: string): HookOutput => {
  const found = locate(path)
  if (!found) return undefined
  const note = touched(input.session_id, found.repo, found.lines)
  if (note === undefined) return undefined
  logFire(input, 'behavior-map-guard:touched-entries', found.relative)
  return context(input, note)
}

// A Bash command cannot be refused before it runs, since its paths are unknown: after it changed code, the guard adds the same notes as context.
// It sees only the git repo of the session's working directory, and only the main agent's commands.
// A marker per call: its change time is set just before the command runs, and a parallel call cannot move it.
const marker = (input: HookInput) => sessionPath(GUARD, input.session_id, `${safe(input.tool_use_id ?? 'call')}.marker`)

const beforeBash = (input: HookInput): HookOutput => {
  mkdirSync(stateDir(), { recursive: true })
  writeFileSync(marker(input), '')
  return undefined
}

const afterBash = (input: HookInput): HookOutput => {
  const mark = marker(input)
  if (!existsSync(mark)) return undefined
  try {
    const top = run(['git', 'rev-parse', '--show-toplevel'], { cwd: input.cwd })
    const repo = top.stdout.trim()
    if (top.exitCode !== 0 || SCRATCH.test(`${repo}/`)) return undefined
    // Changed, staged, renamed, and untracked paths; a rename's old path follows its new one and is skipped.
    const status = run(['git', '--no-optional-locks', 'status', '--porcelain=v1', '-z', '--untracked-files=all'], { cwd: repo })
    if (status.exitCode !== 0) return undefined
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
      const found = run(['find', ...dirty.slice(i, i + CHUNK).map(path => `./${path}`), '-maxdepth', '0', '-cnewer', mark, '-print'], { cwd: repo })
      files.push(...found.stdout.split('\n').filter(line => line !== '').map(line => line.slice(2)))
    }
    if (files.length === 0) return undefined
    const map = run([BEHAVIOR_MAP, 'affected', '--', ...files], { cwd: repo })
    if (map.exitCode !== 0) return undefined
    const lines = map.stdout.split('\n')
    const notes: string[] = []
    // Docs-only and test-only files need no area, so a directory counts only for a changed code file in it.
    const codeDirs = new Set(files.filter(file => !DOCS_OR_TESTS.test(file)).map(file => (file.includes('/') ? file.slice(0, file.lastIndexOf('/')) : '.')))
    // Its own key: a note does not use up the Edit refusal for the same directory.
    const unmapped = unmappedDirs(lines).filter(dir => codeDirs.has(dir) && claimOnce(GUARD, input.session_id, `${repo}\0noted\0${dir}`))
    if (unmapped.length > 0) {
      logFire(input, 'behavior-map-guard:unmapped-shell', unmapped.join(', '))
      notes.push(
        `${GUARD}: this command changed code in ${unmapped.join(', ')} in ${repo}, which has no behavior-map area. ` +
          'Map it now: k-behavior-map skill, area init. ' +
          'For a file in the repo root or a shared directory, add it as a file anchor to the closest entry of an existing area instead; with no area yet, map the subsystem it serves first.',
      )
    }
    const note = touched(input.session_id, repo, lines)
    if (note !== undefined) {
      notes.push(note)
      logFire(input, 'behavior-map-guard:touched-entries', files.join(', '))
    }
    return notes.length === 0 ? undefined : context(input, notes.join('\n\n'))
  } finally {
    rmSync(mark, { force: true })
  }
}

export const handle = (input: HookInput): HookOutput => {
  const before = input.hook_event_name === 'PreToolUse'
  if (input.tool_name === 'Bash') {
    if (input.agent_id !== undefined) return undefined
    const command = input.tool_input?.command
    if (before) return typeof command === 'string' && WRITES.test(command) ? beforeBash(input) : undefined
    return afterBash(input)
  }
  const path = input.tool_input?.notebook_path ?? input.tool_input?.file_path
  if (typeof path !== 'string' || !path.startsWith('/') || SCRATCH.test(path)) return undefined
  if (before) return beforeEdit(input, path)
  // A failed edit changed nothing to note.
  return input.hook_event_name === 'PostToolUse' ? afterEdit(input, path) : undefined
}
