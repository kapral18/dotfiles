import type { SidebarsConfig } from '@docusaurus/plugin-content-docs'

// Keep the visible navigation domain-first instead of mirroring every source
// folder. The markdown still lives under `docs/topics/**` for stable URLs, but
// the sidebar surfaces the real sections directly.
const sidebars: SidebarsConfig = {
  docs: [
    {
      type: 'category',
      label: '🏁 Introduction',
      collapsed: false,
      link: { type: 'doc', id: 'intro/index' },
      items: [
        'intro/getting-started',
        'intro/architecture',
        'intro/day-in-the-life',
        'intro/learning-paths',
        'intro/new-machine-bootstrap',
      ],
    },
    {
      type: 'category',
      label: '🏗️ Chezmoi',
      link: { type: 'doc', id: 'topics/core/chezmoi/index' },
      items: [
        'topics/core/chezmoi/debug-hooks',
        'topics/core/chezmoi/refresh-externals',
        'topics/core/chezmoi/update',
        'topics/core/chezmoi/verify-templates',
      ],
    },
    {
      type: 'category',
      label: '📦 Packages',
      link: { type: 'doc', id: 'topics/core/packages/index' },
      items: [
        {
          type: 'category',
          label: '🗂️ Package catalog',
          link: { type: 'doc', id: 'topics/core/packages/catalog/index' },
          items: [
            'topics/core/packages/catalog/ai-and-agent-tooling',
            'topics/core/packages/catalog/developer-workflow',
            'topics/core/packages/catalog/terminal-files-and-data',
            'topics/core/packages/catalog/macos-apps-and-system',
            'topics/core/packages/catalog/media-personal-and-custom',
            'topics/core/packages/catalog/languages-and-runtimes',
          ],
        },
        'topics/core/packages/sources-and-scope',
        'topics/core/packages/reconcile-behavior',
        'topics/core/packages/verification',
        'topics/core/packages/homebrew',
        'topics/core/packages/mise',
        'topics/core/packages/cargo',
        'topics/core/packages/go',
        'topics/core/packages/ruby',
        'topics/core/packages/yarn',
        'topics/core/packages/uv',
        'topics/core/packages/custom',
        'topics/core/packages/llama-cpp-model',
      ],
    },
    {
      type: 'category',
      label: '🔐 Git & identity',
      link: { type: 'doc', id: 'topics/workflow/git-identity/index' },
      items: [
        'topics/workflow/git-identity/git-config',
        'topics/workflow/git-identity/identity-and-keys',
        'topics/workflow/git-identity/gh-extension',
        'topics/workflow/git-identity/switch-identity',
        'topics/workflow/git-identity/worktrees',
        'topics/workflow/git-identity/worktree-subcommands',
        'topics/workflow/git-identity/worktree-github-integration',
      ],
    },
    { type: 'doc', id: 'topics/workflow/shell-fish', label: '🐟 Fish shell' },
    { type: 'doc', id: 'topics/workflow/terminals', label: '🖥️ Terminals' },
    {
      type: 'category',
      label: '🪟 Tmux',
      link: { type: 'doc', id: 'topics/workflow/tmux/index' },
      items: [
        'topics/workflow/tmux/pickers',
        'topics/workflow/tmux/session-picker',
        'topics/workflow/tmux/session-picker-mechanics',
        'topics/workflow/tmux/github-picker',
        'topics/workflow/tmux/github-picker-mechanics',
        'topics/workflow/tmux/lowfi',
        'topics/workflow/tmux/popups-and-tools',
      ],
    },
    {
      type: 'category',
      label: '⚡ Custom commands',
      link: { type: 'doc', id: 'topics/workflow/custom-commands/index' },
      items: [
        'topics/workflow/custom-commands/high-leverage',
        'topics/workflow/custom-commands/catalog',
      ],
    },
    {
      type: 'category',
      label: '📝 Neovim',
      link: { type: 'doc', id: 'topics/editor/neovim/index' },
      items: [
        'topics/editor/neovim/architecture-and-source',
        {
          type: 'category',
          label: '📊 PackDashboard',
          link: { type: 'doc', id: 'topics/editor/neovim/pack-dashboard/index' },
          items: [
            'topics/editor/neovim/pack-dashboard/loading-and-version-policy',
            'topics/editor/neovim/pack-dashboard/dashboard-ui',
            'topics/editor/neovim/pack-dashboard/operations-and-commands',
          ],
        },
        {
          type: 'category',
          label: '🧰 Language tooling',
          link: { type: 'doc', id: 'topics/editor/neovim/language-tooling/index' },
          items: [
            'topics/editor/neovim/language-tooling/parsers-and-filetypes',
            'topics/editor/neovim/language-tooling/lsp-and-source-jumps',
            'topics/editor/neovim/language-tooling/progress-and-prose',
          ],
        },
        {
          type: 'category',
          label: '🔁 Workflows',
          link: { type: 'doc', id: 'topics/editor/neovim/workflows/index' },
          items: [
            'topics/editor/neovim/workflows/keymaps-search-and-navigation',
            'topics/editor/neovim/workflows/git-and-quality-of-life',
            'topics/editor/neovim/workflows/ide-translation-and-verification',
          ],
        },
        {
          type: 'category',
          label: '🔌 Local plugins',
          link: { type: 'doc', id: 'topics/editor/neovim/local-plugins/index' },
          items: [
            'topics/editor/neovim/local-plugins/testing-and-commit-ai',
            'topics/editor/neovim/local-plugins/ownership-refactors-and-tmux',
            'topics/editor/neovim/local-plugins/navigation-and-quickfix',
            'topics/editor/neovim/local-plugins/screenshots-and-window-ergonomics',
          ],
        },
      ],
    },
    {
      type: 'category',
      label: '🍎 macOS',
      link: { type: 'doc', id: 'topics/macos/index' },
      items: [
        'topics/macos/defaults-and-apply-flow',
        'topics/macos/hotkeys-and-launchers',
        'topics/macos/icons-and-scheduled-jobs',
        'topics/macos/verification',
        'topics/macos/custom-app-icons',
      ],
    },
    { type: 'doc', id: 'topics/security/security-and-secrets', label: '🔒 Security' },
    { type: 'doc', id: 'topics/code-quality/formatting', label: '✅ Code quality' },
    {
      type: 'category',
      label: '🤖 AI Assistants',
      link: { type: 'doc', id: 'topics/ai-assistants/index' },
      items: [
        {
          type: 'category',
          label: '📜 System Prompt (SOP)',
          link: { type: 'doc', id: 'topics/ai-assistants/system-prompt/index' },
          items: [
            'topics/ai-assistants/system-prompt/source-of-truth',
            'topics/ai-assistants/system-prompt/truth-and-verification',
            'topics/ai-assistants/system-prompt/execution-workflow',
            'topics/ai-assistants/system-prompt/side-effect-gates',
            'topics/ai-assistants/system-prompt/code-quality-and-dotfiles-policy',
          ],
        },
        {
          type: 'category',
          label: '🧩 Skills',
          link: { type: 'doc', id: 'topics/ai-assistants/skills/index' },
          items: [
            'topics/ai-assistants/skills/review-and-delivery',
            'topics/ai-assistants/skills/repo-workflow-and-code-intelligence',
            'topics/ai-assistants/skills/memory-and-orchestration',
            'topics/ai-assistants/skills/elastic-and-kibana',
            'topics/ai-assistants/skills/external-tools-and-media',
          ],
        },
        'topics/ai-assistants/subagents',
        {
          type: 'category',
          label: '🔎 Review workflow',
          link: { type: 'doc', id: 'topics/ai-assistants/reviews/index' },
          items: [
            'topics/ai-assistants/reviews/agent-review-topology',
            'topics/ai-assistants/reviews/base-context-and-truth',
            'topics/ai-assistants/reviews/post-review-and-light-review',
            'topics/ai-assistants/reviews/replies-publication-and-history',
          ],
        },
        {
          type: 'category',
          label: '🧠 Agent memory',
          link: { type: 'doc', id: 'topics/ai-assistants/knowledge-base/index' },
          items: [
            'topics/ai-assistants/knowledge-base/hook-memory',
            'topics/ai-assistants/knowledge-base/ai-kb',
            'topics/ai-assistants/knowledge-base/cross-agent-memory',
          ],
        },
        {
          type: 'category',
          label: '🕹️ Ralph orchestrator',
          link: { type: 'doc', id: 'topics/ai-assistants/ralph/index' },
          items: [
            'topics/ai-assistants/ralph/roles-and-diversity',
            'topics/ai-assistants/ralph/state-and-runtime',
            'topics/ai-assistants/ralph/dashboard-and-tmux',
            'topics/ai-assistants/ralph/verification',
          ],
        },
        'topics/ai-assistants/mcp',
        'topics/ai-assistants/model-registry',
        {
          type: 'category',
          label: '⚙️ Tool configs',
          link: { type: 'doc', id: 'topics/ai-assistants/tool-configs/index' },
          items: [
            'topics/ai-assistants/tool-configs/cursor-and-prompt-wrap',
            'topics/ai-assistants/tool-configs/profile-merging',
            'topics/ai-assistants/tool-configs/claude-gemini',
            'topics/ai-assistants/tool-configs/pi',
            'topics/ai-assistants/tool-configs/other-harnesses',
          ],
        },
        'topics/ai-assistants/rtk',
        {
          type: 'category',
          label: '🦙 llama.cpp local inference',
          link: { type: 'doc', id: 'topics/ai-assistants/llama-cpp/index' },
          items: [
            'topics/ai-assistants/llama-cpp/install-and-models',
            'topics/ai-assistants/llama-cpp/router-control-plane',
            'topics/ai-assistants/llama-cpp/pi-provider',
            'topics/ai-assistants/llama-cpp/launchers',
          ],
        },
        'topics/ai-assistants/reviewing-diffs',
      ],
    },
    {
      type: 'category',
      label: '🧭 Reference',
      link: {
        type: 'generated-index',
        title: 'Reference',
        description: 'Lookup-style pages: reference map, FAQ, implementation coverage, and troubleshooting.',
      },
      items: [
        'reference/reference-map',
        'reference/implementation-coverage',
        'reference/ai-reference',
        'reference/faq',
        'reference/troubleshooting',
      ],
    },
  ],
}

export default sidebars
