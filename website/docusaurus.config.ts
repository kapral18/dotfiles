import { themes as prismThemes } from 'prism-react-renderer'
import type { Config } from '@docusaurus/types'
import type * as Preset from '@docusaurus/preset-classic'

// CommonJS plugin — rewrites cross-repo relative links (../home/..., ../../README.md)
// into absolute GitHub URLs at build time. Keeps the docs source canonical for
// agents reading the repo while the website serves working external links.
import rewriteCrossRepoLinks from './src/remark/cross-repo-links.js'
import localSearchPlugin from './src/plugins/local-search'

const config: Config = {
  title: 'kapral18/dotfiles',
  tagline: 'Personal Developer Environment',
  favicon: 'img/favicon.svg',

  url: 'https://kapral18.github.io',
  baseUrl: '/dotfiles/',

  organizationName: 'kapral18',
  projectName: 'dotfiles',
  trailingSlash: false,

  // Existing markdown was authored without MDX in mind (uses literals like
  // `<branch>` or `{ key: value }` in prose) so we serve it as plain markdown.
  // The MDX parser would otherwise treat those as expressions and fail.
  markdown: {
    format: 'md',
    hooks: {
      // `onBrokenMarkdownLinks` moved here in 3.10; warn rather than throw so
      // the build is forgiving while we iterate on the docs.
      onBrokenMarkdownLinks: 'warn',
    },
  },

  onBrokenLinks: 'warn',
  onBrokenAnchors: 'warn',
  onDuplicateRoutes: 'warn',

  i18n: {
    defaultLocale: 'en',
    locales: [ 'en' ],
  },

  plugins: [
    // Local-search plugin: builds a MiniSearch index from `../docs/` markdown
    // sources and writes it to `static/search-index.json`. The swizzled
    // SearchBar (src/theme/SearchBar) lazy-fetches it on first cmd+k.
    localSearchPlugin,
  ],

  presets: [
    [
      'classic',
      {
        docs: {
          // Markdown source-of-truth lives at the repo root in `docs/`. We
          // intentionally do NOT move it under `website/` — the AGENTS.md
          // SOP rule "reflect changes in `docs/`" stays literal, and AI
          // agents reading the repo continue to find docs where they expect.
          path: '../docs',
          routeBasePath: '/',
          sidebarPath: './sidebars.ts',
          // Docusaurus appends the path relative to `path`, so the real
          // GitHub source lives one level deeper than `path` would suggest.
          editUrl: 'https://github.com/kapral18/dotfiles/edit/main/docs/',
          showLastUpdateTime: true,
          showLastUpdateAuthor: false,
          // Run BEFORE Docusaurus's built-in link transformer so the link
          // checker sees absolute GitHub URLs instead of unresolved relative
          // paths. `remarkPlugins` runs *after* the defaults, which is too late.
          beforeDefaultRemarkPlugins: [ rewriteCrossRepoLinks ],
        },
        blog: false,
        theme: {
          customCss: './src/css/custom.css',
        },
      } satisfies Preset.Options,
    ],
  ],

  themeConfig: {
    colorMode: {
      defaultMode: 'dark',
      respectPrefersColorScheme: true,
    },
    navbar: {
      title: 'kapral18/dotfiles',
      items: [
        { to: '/', label: 'Docs', position: 'left' },
        {
          href: 'https://github.com/kapral18/dotfiles',
          label: 'GitHub',
          position: 'right',
        },
      ],
    },
    footer: {
      style: 'dark',
      links: [
        {
          title: 'Repository',
          items: [
            { label: 'GitHub', href: 'https://github.com/kapral18/dotfiles' },
            { label: 'Issues', href: 'https://github.com/kapral18/dotfiles/issues' },
          ],
        },
        {
          title: 'Read the source',
          items: [
            { label: 'docs/ on GitHub', href: 'https://github.com/kapral18/dotfiles/tree/main/docs' },
            { label: 'home/ on GitHub', href: 'https://github.com/kapral18/dotfiles/tree/main/home' },
          ],
        },
      ],
      copyright: 'Built with Docusaurus.',
    },
    prism: {
      theme: prismThemes.github,
      darkTheme: prismThemes.dracula,
      // Prism doesn't ship a `fish` grammar; bash is close enough for fish
      // snippets and is what most highlighting libraries fall back to.
      additionalLanguages: [ 'bash', 'diff', 'ini', 'lua', 'shell-session', 'toml', 'yaml' ],
    },
  } satisfies Preset.ThemeConfig,
}

export default config
