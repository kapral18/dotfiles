import { themes as prismThemes } from 'prism-react-renderer'
import type { Config } from '@docusaurus/types'
import type * as Preset from '@docusaurus/preset-classic'

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

  // Examples such as <branch> and { key: value } must stay literal, not MDX.
  markdown: {
    format: 'md',
    hooks: {
      onBrokenMarkdownLinks: 'throw',
    },
  },

  onBrokenLinks: 'throw',
  onBrokenAnchors: 'throw',
  onDuplicateRoutes: 'warn',

  i18n: {
    defaultLocale: 'en',
    locales: [ 'en' ],
  },

  plugins: [
    localSearchPlugin,
  ],

  presets: [
    [
      'classic',
      {
        docs: {
          // Share the repository's source docs instead of maintaining a site copy.
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
        { to: '/topics/ai-assistants', label: 'AI assistants', position: 'left' },
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
