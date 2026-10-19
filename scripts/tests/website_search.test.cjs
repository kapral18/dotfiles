const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const { createRequire } = require('node:module')
const { test } = require('node:test')
const vm = require('node:vm')

const repo = path.resolve(__dirname, '../..')
const siteRequire = createRequire(path.join(repo, 'website/package.json'))
const React = siteRequire('react')
const { act, create } = siteRequire('react-test-renderer')
const MiniSearch = siteRequire('minisearch')
const ts = siteRequire('typescript')
const source = process.env.SEARCH_BAR_SOURCE || path.join(repo, 'website/src/theme/SearchBar/index.tsx')
const compiled = ts.transpileModule(fs.readFileSync(source, 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.React, esModuleInterop: true },
}).outputText

const index = new MiniSearch({
  fields: [ 'title', 'pageTitle', 'headings', 'body' ],
  storeFields: [ 'pageTitle', 'title', 'url' ],
})
index.add({ id: 'worktrees', title: 'Worktrees', pageTitle: 'Git', headings: '', body: 'Create a branch', url: '/dotfiles/worktrees' })
const response = (ok = true) => ({ ok, status: ok ? 200 : 503, text: async () => JSON.stringify(index) })

async function harness(t, fetchResponse) {
  let requests = 0
  const navigations = []
  const listeners = new Map()
  const dialog = { open: false, showModal() { this.open = true }, close() { this.open = false } }
  const modules = {
    react: React,
    'react-dom': { createPortal: (children) => children },
    minisearch: MiniSearch,
    '@docusaurus/Link': (props) => React.createElement('a', props),
    '@docusaurus/useBaseUrl': () => '/dotfiles/search-index.json',
    '@docusaurus/BrowserOnly': ({ children }) => children(),
    '@docusaurus/router': { useHistory: () => ({ push: (url) => navigations.push(url) }) },
    './styles.module.css': {},
  }
  const module = { exports: {} }
  const load = vm.runInNewContext(`(function(require, module, exports) { ${compiled}\n})`, {
    console: { error() {} },
    navigator: { platform: 'MacIntel' },
    HTMLElement: class {},
    document: {
      body: {},
      addEventListener: (name, fn) => listeners.set(name, fn),
      removeEventListener: (name) => listeners.delete(name),
    },
    fetch: async () => fetchResponse(++requests),
    queueMicrotask,
  }, { filename: source })
  load((name) => {
    assert.ok(Object.hasOwn(modules, name), `Unexpected module: ${name}`)
    return modules[name]
  }, module, module.exports)

  let tree
  await act(async () => {
    tree = create(React.createElement(module.exports.default), {
      createNodeMock: ({ type }) => type === 'dialog' ? dialog : { focus() {}, children: [] },
    })
  })
  t.after(() => act(() => tree.unmount()))
  const input = () => tree.root.findByType('input')
  return {
    tree, dialog, navigations,
    requests: () => requests,
    text: () => JSON.stringify(tree.toJSON()),
    open: () => act(async () => tree.root.findByProps({ 'aria-label': 'Search docs' }).props.onClick()),
    query: (value) => act(async () => input().props.onChange({ target: { value } })),
    key: (key) => act(async () => input().props.onKeyDown({ key, preventDefault() {} })),
    close: () => act(async () => tree.root.findByType('dialog').props.onCancel()),
    hotkey: () => act(async () => listeners.get('keydown')({ key: 'k', metaKey: true, preventDefault() {} })),
  }
}

test('WHEN the index request fails SHOULD stop retrying and explain the failure', async (t) => {
  const h = await harness(t, (attempt) => {
    if (attempt === 1) throw new Error('offline')
    return new Promise(() => {})
  })
  await h.open()
  await h.query('worktrees')
  assert.equal(h.requests(), 1)
  assert.match(h.text(), /unavailable/i)
  assert.doesNotMatch(h.text(), /No results/)
})

test('WHEN HTTP fails SHOULD reject even a parseable response body', async (t) => {
  const h = await harness(t, () => response(false))
  await h.open()
  await h.query('worktrees')
  assert.match(h.text(), /unavailable/i)
  assert.equal(h.tree.root.findAllByProps({ role: 'option' }).length, 0)
})

test('WHEN a failed search is reopened SHOULD retry and return results', async (t) => {
  const h = await harness(t, (attempt) => {
    if (attempt === 1) throw new Error('offline')
    return response()
  })
  await h.open()
  assert.equal(h.requests(), 1)
  await h.close()
  await h.open()
  await h.query('worktrees')
  assert.equal(h.requests(), 2)
  assert.equal(h.tree.root.findAllByProps({ role: 'option' }).length, 1)
  assert.doesNotMatch(h.text(), /unavailable/i)
})

test('WHEN selecting a result with Enter SHOULD navigate and reuse the loaded index', async (t) => {
  const h = await harness(t, () => response())
  await h.open()
  assert.equal(h.dialog.open, true)
  await h.query('worktrees')
  const input = h.tree.root.findByType('input')
  assert.equal(input.props.role, 'combobox')
  assert.equal(input.props['aria-label'], 'Search documentation')
  assert.equal(input.props['aria-activedescendant'], h.tree.root.findByProps({ role: 'option' }).props.id)
  await h.key('Enter')
  assert.deepEqual(h.navigations, [ '/dotfiles/worktrees' ])
  assert.equal(h.dialog.open, false)
  await h.open()
  assert.equal(h.requests(), 1)
  assert.equal(h.tree.root.findByType('input').props.value, '')
})

test('WHEN toggling the shortcut SHOULD clear the previous query on close', async (t) => {
  const h = await harness(t, () => response())
  await h.hotkey()
  await h.query('missing-query')
  assert.match(h.text(), /No results/)
  await h.hotkey()
  await h.hotkey()
  assert.equal(h.tree.root.findByType('input').props.value, '')
  assert.equal(h.requests(), 1)
})
