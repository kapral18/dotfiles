/**
 * Keep repo-relative source links usable outside the Docusaurus content tree.
 * Links leaving docs/ become GitHub URLs; images use raw.githubusercontent.com.
 * Run before Docusaurus's link resolver, which cannot bundle those sources.
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
  // A directory whose name contains a dot needs a trailing slash.
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
