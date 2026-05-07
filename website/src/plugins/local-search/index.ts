/**
 * Local-search plugin: walks the markdown sources under `../docs/`, splits
 * each file into per-H2 sections, builds a MiniSearch index with one document
 * per section, and writes it to `static/search-index.json` so the swizzled
 * SearchBar component can lazy-fetch it from `/<baseUrl>/search-index.json`.
 *
 * Per-section indexing means a search for "1password" surfaces the exact
 * `## 1Password` section (linked with `#1password` anchor) instead of just the
 * page that happens to mention it. Anchor slugs are produced by
 * `github-slugger`, the same algorithm Docusaurus uses for heading IDs, so the
 * generated URLs scroll the user to the right spot on click.
 *
 * Runs once on plugin load (i.e. once per `pnpm start` and once per
 * `pnpm build`). In dev mode the index does NOT auto-refresh on doc edits;
 * restart the dev server to reindex.
 */

import path from 'path'
import { promises as fs } from 'fs'
import matter from 'gray-matter'
import MiniSearch from 'minisearch'
import GithubSlugger from 'github-slugger'
import type { LoadContext, Plugin } from '@docusaurus/types'

interface IndexedDoc {
  id: string
  url: string
  pageTitle: string
  title: string
  headings: string
  body: string
}

interface Section {
  /** Empty string for the page intro (content above the first H2). */
  heading: string
  /** Markdown body of just this section (excludes the heading line itself). */
  body: string
}

const PLUGIN_NAME = 'docusaurus-plugin-local-search'

export default function localSearchPlugin(
  context: LoadContext,
): Plugin<undefined> {
  const docsDir = path.resolve(context.siteDir, '..', 'docs')
  const outPath = path.join(context.siteDir, 'static', 'search-index.json')

  return {
    name: PLUGIN_NAME,
    async loadContent() {
      const docs = await collectDocs(docsDir, context.baseUrl)
      const search = new MiniSearch({
        idField: 'id',
        fields: [ 'title', 'pageTitle', 'headings', 'body' ],
        storeFields: [ 'pageTitle', 'title', 'url' ],
      })
      search.addAll(docs)
      await fs.mkdir(path.dirname(outPath), { recursive: true })
      await fs.writeFile(outPath, JSON.stringify(search.toJSON()))
      return undefined
    },
  }
}

async function collectDocs(docsDir: string, baseUrl: string): Promise<IndexedDoc[]> {
  const files = await listMarkdownFiles(docsDir)
  const docs: IndexedDoc[] = []
  for (const rel of files) {
    const raw = await fs.readFile(path.join(docsDir, rel), 'utf8')
    const { data, content } = matter(raw)
    const pageUrl = computeUrl(rel, data, baseUrl)
    const pageTitle = String(data.title ?? extractH1(content) ?? defaultTitle(rel))
    const sections = splitSections(content)
    // Each markdown file has its own slug counter so duplicate H2 text within
    // the same page gets `-1`, `-2` suffixes the same way Docusaurus does.
    const slugger = new GithubSlugger()
    for (const section of sections) {
      const isIntro = section.heading === ''
      const url = isIntro ? pageUrl : `${pageUrl}#${slugger.slug(section.heading)}`
      const title = isIntro ? pageTitle : section.heading
      docs.push({
        id: url,
        url,
        pageTitle,
        title,
        headings: extractHeadings(section.body).join(' '),
        body: stripMarkdown(section.body),
      })
    }
  }
  return docs
}

async function listMarkdownFiles(dir: string): Promise<string[]> {
  const out: string[] = []
  async function walk(current: string, prefix: string) {
    const entries = await fs.readdir(current, { withFileTypes: true })
    for (const entry of entries) {
      const rel = prefix ? `${prefix}/${entry.name}` : entry.name
      const full = path.join(current, entry.name)
      if (entry.isDirectory()) {
        await walk(full, rel)
      } else if (entry.isFile() && entry.name.endsWith('.md')) {
        out.push(rel)
      }
    }
  }
  await walk(dir, '')
  return out.sort()
}

/**
 * Split markdown into the page intro + one chunk per `##` heading. Headings
 * inside fenced code blocks are ignored so a `## comment` line in a Bash
 * snippet doesn't produce a phantom section. H1 lines are skipped — the page
 * title is computed separately and there's no anchor for them anyway. H3+ are
 * left inside their parent section's body so they remain searchable but don't
 * each spawn their own document (which would 3-5x the index size).
 */
function splitSections(content: string): Section[] {
  const sections: Section[] = []
  let current: Section = { heading: '', body: '' }
  let inFence = false
  for (const line of content.split('\n')) {
    if (/^```/.test(line)) inFence = !inFence
    if (!inFence) {
      const h2 = line.match(/^##\s+(.+?)\s*$/)
      if (h2) {
        if (current.heading !== '' || current.body.trim() !== '') sections.push(current)
        current = { heading: h2[1], body: '' }
        continue
      }
      // Drop the H1 line from the intro section — its text is captured in
      // `pageTitle`, and keeping it would add noise to body matches.
      if (current.heading === '' && /^#\s+/.test(line)) continue
    }
    current.body += (current.body ? '\n' : '') + line
  }
  if (current.heading !== '' || current.body.trim() !== '') sections.push(current)
  return sections
}

function computeUrl(filePath: string, frontmatter: Record<string, unknown>, baseUrl: string): string {
  if (typeof frontmatter.slug === 'string') {
    return joinUrl(baseUrl, frontmatter.slug)
  }
  let urlPath = filePath.replace(/\.md$/, '')
  if (urlPath === 'index') {
    return joinUrl(baseUrl, '/')
  }
  if (urlPath.endsWith('/index')) {
    urlPath = urlPath.slice(0, -'/index'.length)
  }
  return joinUrl(baseUrl, urlPath)
}

function joinUrl(base: string, suffix: string): string {
  const b = base.endsWith('/') ? base.slice(0, -1) : base
  const s = suffix.startsWith('/') ? suffix : `/${suffix}`
  if (s === '/') return `${b}/`
  return `${b}${s}`
}

function defaultTitle(filePath: string): string {
  const name = path.basename(filePath, '.md')
  if (name === 'index') {
    const parent = path.basename(path.dirname(filePath))
    return parent === '.' ? 'Home' : titleCase(parent)
  }
  return titleCase(name)
}

function titleCase(slug: string): string {
  return slug
    .split('-')
    .filter(Boolean)
    .map((w) => w[0].toUpperCase() + w.slice(1))
    .join(' ')
}

function extractH1(content: string): string | null {
  const m = content.match(/^#\s+(.+)$/m)
  return m ? m[1].trim() : null
}

function extractHeadings(content: string): string[] {
  return Array.from(content.matchAll(/^#{2,}\s+(.+)$/gm), (m) => m[1].trim())
}

/**
 * Strip the noisiest markdown so MiniSearch's tokenizer sees mostly prose.
 * Not perfect — we intentionally keep this small and dependency-free rather
 * than pulling in a full markdown AST. Code blocks become a single space so
 * they don't inflate the index, and inline punctuation is replaced with
 * spaces to keep word boundaries.
 */
function stripMarkdown(content: string): string {
  return content
    .replace(/```[\s\S]*?```/g, ' ')
    .replace(/`[^`\n]+`/g, ' ')
    .replace(/!\[[^\]]*\]\([^)]+\)/g, ' ')
    .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
    .replace(/^[#>*\-_+]+\s*/gm, '')
    .replace(/[*_~]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
}
