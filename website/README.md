# Docusaurus website

Public docs site for [`kapral18/dotfiles`](https://github.com/kapral18/dotfiles), serving the markdown under [`../docs/`](../docs/) at <https://kapral18.github.io/dotfiles/>.

## Local development

From the repo root:

```bash
make docs           # start the dev server at http://localhost:3000/dotfiles/
make docs-build     # production build into website/build/
make docs-serve     # serve the production build locally (matches GitHub Pages)
make docs-clean     # clear the .docusaurus/ cache
```

The root `package.json` exposes the same flow for npm users:

```bash
npm run docs
npm run docs:build
npm run docs:serve
npm run docs:clean
```

The `make` targets and npm scripts auto-install `website/node_modules/` on first run via the mise-managed pnpm binary and `--frozen-lockfile`. The dev server hot-reloads on changes under `docs/` and `website/`.

If you'd rather drive pnpm directly, the equivalent is `pnpm --dir website {start,build,serve,clear}` from the repo root, or `cd website && pnpm <script>`.

### pnpm version

The website uses the mise-managed pnpm binary (`pnpm --version` should match the version pinned in `~/.config/mise/config.toml`) and records that expectation in the `packageManager` field in [`package.json`](package.json); CI enables it through corepack from the same field. If `pnpm-lock.yaml` changes unexpectedly, rerun the install with that pnpm version.

[`pnpm-workspace.yaml`](pnpm-workspace.yaml) holds the dependency build-script policy pnpm 11+ requires (`core-js` stays off; its postinstall only prints a banner).

The repo root has a scripts-only `package.json` so `npm run docs` works from the checkout root. Its `pnpm-workspace.yaml` sets `verifyDepsBeforeRun: false`; without it pnpm 11+ runs an install before every root `pnpm run` and leaves an empty `pnpm-lock.yaml` plus a stub `node_modules/` behind.

## Deployment

Pushing to `main` runs `.github/workflows/deploy-docs.yml`, which builds and uploads the static site to GitHub Pages. The workflow only runs when files under `docs/`, `website/`, or the workflow itself change.

## Architecture

- Markdown source-of-truth lives in [`../docs/`](../docs/) — do not move it. Docusaurus reads it via `path: '../docs'` in `docusaurus.config.ts`.
- `markdown.format: 'md'` is set so files using `<placeholder>` syntax don't trip the MDX parser.
- Sidebar navigation is explicit and domain-first in [`sidebars.ts`](sidebars.ts). The markdown can keep stable source paths under `docs/topics/**` without forcing a generic `Topics` or `Core` wrapper into the visible docs.
- Cross-repo links (e.g. `../home/...`) are rewritten to absolute GitHub URLs at build time by [`src/remark/cross-repo-links.js`](src/remark/cross-repo-links.js).
- This directory is outside `home/`, so chezmoi does not manage it.

### Search

Search uses a locally generated index:

- [`src/plugins/local-search`](src/plugins/local-search/index.ts) — Docusaurus plugin. On `loadContent`, walks `../docs/`, splits each file at `##` boundaries, and builds a [MiniSearch](https://lucaong.github.io/minisearch/) index with one document per section. [`github-slugger`](https://github.com/Flet/github-slugger) generates section anchors. The output is `static/search-index.json`.
- [`src/theme/SearchBar`](src/theme/SearchBar/index.tsx) — swizzled SearchBar slot. Renders the `⌘ K` / `Ctrl K` trigger in the navbar and a modal with keyboard navigation. Each result shows the section title with the page title as a breadcrumb. Lazy-fetches the index on first open. `Esc` closes, `↑↓` navigate, `Enter` opens, `/` also opens search when not typing in another input. Field weights: `title 4×`, `pageTitle 3×`, `headings 2×`, `body 1×`.

`static/search-index.json` is gitignored — it's rebuilt every `pnpm build` / `pnpm start`. Edits to docs during dev mode do **not** auto-refresh the index; restart the dev server (`make docs`) to reindex.

The search dialog labels loading, failed loading, and no matches separately. A failed load retries when search is reopened; a loaded index is reused. The native modal dialog keeps keyboard focus inside it. Arrow keys select a result and Enter opens it; Escape, Close, or the shortcut dismisses search and clears the query.

Component tests use React's test renderer with an in-memory index and stubbed fetch, routing, and dialog APIs. They run through `make check` when search sources change, without a browser or network requests. Install the website dependencies first with `pnpm --dir website install --frozen-lockfile`.
