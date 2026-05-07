/**
 * Remark plugin: rewrite relative markdown/image links that escape the docs/
 * tree (i.e. point at files elsewhere in the repo such as `home/...`,
 * `tools/...`, the root `README.md`, root dotfiles like `.prettierrc`, etc.)
 * into absolute GitHub URLs at build time.
 *
 * Why this exists:
 *   - The docs deliberately reference scripts/configs under `home/` and other
 *     repo-root paths, which are outside the Docusaurus content tree.
 *   - Docusaurus's default link resolver either warns (broken link) or fails
 *     the build (when it tries to bundle a non-`.md` target as a webpack
 *     module — e.g. a directory like `home/Alfred.alfredpreferences/`).
 *   - Keeping the source markdown using repo-relative paths means agents
 *     reading `docs/` directly (via the AGENTS.md "reflect changes in `docs/`"
 *     rule) still get working links.
 *
 * Algorithm (per link/image node):
 *   1. Skip absolute, protocol, anchor-only, and empty URLs.
 *   2. Resolve the URL against the source file's directory using `path.resolve`.
 *   3. If the resolved path is inside `docs/`, leave the link alone — Docusaurus
 *      handles intra-docs routing natively.
 *   4. Otherwise compute the path relative to the repo root and rewrite to:
 *        - links  → `https://github.com/<owner>/<repo>/blob|tree/main/<path>`
 *        - images → `https://raw.githubusercontent.com/<owner>/<repo>/main/<path>`
 *      Trailing slash or absence of a file-like name → `tree/main`, else `blob/main`.
 */

const path = require('path')

const REPO_BASE = 'https://github.com/kapral18/dotfiles'
const RAW_BASE = 'https://raw.githubusercontent.com/kapral18/dotfiles/main'
const REPO_ROOT = path.resolve(__dirname, '..', '..', '..')
const DOCS_ROOT = path.join(REPO_ROOT, 'docs')

function walk(node, fn) {
  if (!node || typeof node !== 'object') return
  fn(node)
  if (Array.isArray(node.children)) {
    for (const child of node.children) walk(child, fn)
  }
}

function isAbsoluteOrExternal(url) {
  return (
    url.startsWith('http://') ||
    url.startsWith('https://') ||
    url.startsWith('//') ||
    url.startsWith('mailto:') ||
    url.startsWith('#') ||
    url.startsWith('/')
  )
}

function looksLikeFile(basename, hasTrailingSlash) {
  if (hasTrailingSlash) return false
  // Dotfiles like `.prettierrc`, `.gitignore`, `.editorconfig`.
  if (basename.startsWith('.') && !basename.includes('/')) return true
  // Anything with a recognizable extension. Note: this misclassifies the
  // Alfred bundle (`Alfred.alfredpreferences`), but the source markdown
  // always renders that with a trailing slash, which is handled above.
  return /\.[a-zA-Z0-9]+$/.test(basename)
}

function rewriteCrossRepoLinks() {
  return function transformer(tree, file) {
    const sourcePath = file && file.path
    if (!sourcePath) return

    walk(tree, (node) => {
      if (node.type !== 'link' && node.type !== 'image') return
      if (typeof node.url !== 'string' || node.url.length === 0) return
      if (isAbsoluteOrExternal(node.url)) return

      const hashIdx = node.url.indexOf('#')
      const pathPart = hashIdx === -1 ? node.url : node.url.slice(0, hashIdx)
      const hash = hashIdx === -1 ? '' : node.url.slice(hashIdx)
      if (!pathPart) return

      const resolved = path.resolve(path.dirname(sourcePath), pathPart)

      const insideDocs =
        resolved === DOCS_ROOT || resolved.startsWith(DOCS_ROOT + path.sep)
      if (insideDocs) return

      const relativeFromRepo = path.relative(REPO_ROOT, resolved)
      if (!relativeFromRepo || relativeFromRepo.startsWith('..')) return

      if (node.type === 'image') {
        node.url = `${RAW_BASE}/${relativeFromRepo.replace(/\/$/, '')}${hash}`
        return
      }

      const hasTrailingSlash = pathPart.endsWith('/')
      const basename = path.basename(relativeFromRepo)
      const kind = looksLikeFile(basename, hasTrailingSlash) ? 'blob' : 'tree'
      node.url = `${REPO_BASE}/${kind}/main/${relativeFromRepo.replace(/\/$/, '')}${hash}`
    })
  }
}

module.exports = rewriteCrossRepoLinks
module.exports.default = rewriteCrossRepoLinks
