local lazypath = vim.fn.stdpath("data") .. "/lazy/lazy.nvim"

if not (vim.uv or vim.loop).fs_stat(lazypath) then
  -- bootstrap lazy.nvim
  -- stylua: ignore
  vim.fn.system({ "git", "clone", "--filter=blob:none", "https://github.com/folke/lazy.nvim.git", "--branch=stable", lazypath })
end
vim.opt.rtp:prepend(lazypath)

require("lazy").setup({
  rocks = { hererocks = true },
  spec = {
    -- add LazyVim and import its plugins
    { "LazyVim/LazyVim", import = "lazyvim.plugins" },
    -- import any extras modules here
    { import = "lazyvim.plugins.extras.lang.clangd" },
    { import = "lazyvim.plugins.extras.lang.docker" },
    { import = "lazyvim.plugins.extras.lang.go" },
    { import = "lazyvim.plugins.extras.lang.json" },
    { import = "lazyvim.plugins.extras.lang.markdown" },
    { import = "lazyvim.plugins.extras.lang.python" },
    { import = "lazyvim.plugins.extras.lang.rust" },
    { import = "lazyvim.plugins.extras.lang.yaml" },
    { import = "lazyvim.plugins.extras.editor.fzf" },
    { import = "lazyvim.plugins.extras.editor.outline" },
    { import = "lazyvim.plugins.extras.editor.inc-rename" },
    { import = "lazyvim.plugins.extras.coding.nvim-cmp" },
    { import = "lazyvim.plugins.extras.formatting.prettier" },
    { import = "lazyvim.plugins.extras.ai.copilot-chat" },
    { import = "lazyvim.plugins.extras.dap.core" },
    { import = "lazyvim.plugins.extras.dap.nlua" },

    -- Overrides of 3rd party plugins
    { import = "plugins.ai" },
    { import = "plugins.bash" },
    { import = "plugins.bufferline" },
    { import = "plugins.chezmoi" },
    { import = "plugins.cmp" },
    { import = "plugins.dashboard" },
    { import = "plugins.diff" },
    { import = "plugins.disable-flash" },
    { import = "plugins.eslint" },
    { import = "plugins.explorer" },
    { import = "plugins.fish" },
    { import = "plugins.fzf" },
    { import = "plugins.git" },
    { import = "plugins.github" },
    { import = "plugins.gx" },
    { import = "plugins.highlight" },
    { import = "plugins.hlargs" },
    { import = "plugins.html-css" },
    { import = "plugins.jinja" },
    { import = "plugins.jsonl" },
    { import = "plugins.k8s" },
    { import = "plugins.kdl" },
    { import = "plugins.key-analyzer" },
    { import = "plugins.lazydev" },
    { import = "plugins.leap" },
    { import = "plugins.linting" },
    { import = "plugins.live-command" },
    { import = "plugins.log" },
    { import = "plugins.lsp" },
    { import = "plugins.lua" },
    { import = "plugins.lualine" },
    { import = "plugins.markdown" },
    { import = "plugins.marks" },
    { import = "plugins.mason-workaround" },
    { import = "plugins.multi-cursors" },
    { import = "plugins.noice" },
    { import = "plugins.numb" },
    { import = "plugins.nvim-notify" },
    { import = "plugins.osv" },
    { import = "plugins.parinfer" },
    { import = "plugins.python" },
    { import = "plugins.rust" },
    { import = "plugins.search-and-replace" },
    { import = "plugins.session" },
    { import = "plugins.snacks" },
    { import = "plugins.tab-behavior" },
    { import = "plugins.telescope" },
    { import = "plugins.tmux" },
    { import = "plugins.tpope" },
    { import = "plugins.treesitter" },
    { import = "plugins.trouble" },
    { import = "plugins.typescript-tools" },
    { import = "plugins.undotree" },
    { import = "plugins.which-key" },
    { import = "plugins.xml" },
    { import = "plugins.yaml" },

    -- Local plugins (
    -- plugins whose functionality lives in ~/.config/nvim/lua/plugins-local/
    -- or
    -- who use access functionality from ~/.config/nvim/lua/plugins-local-src/
    -- )
    { import = "plugins-local.copy-to-qf" },
    { import = "plugins-local.fzf-filters-lsp" },
    { import = "plugins-local.owner-code-search" },
    { import = "plugins-local.qf" },
    { import = "plugins-local.run-jest-in-split" },
    { import = "plugins-local.save-ai-data" },
    { import = "plugins-local.show-file-owner" },
    { import = "plugins-local.summarize-commit" },
    { import = "plugins-local.switch-src-test" },
    { import = "plugins-local.winbar" },
  },
  change_detection = { enabled = false, notify = false },
  concurrency = 100,
  defaults = {
    -- By default, only LazyVim plugins will be lazy-loaded. Your custom plugins will load during startup.
    -- If you know what you're doing, you can set this to `true` to have all your custom plugins lazy-loaded by default.
    lazy = false,
    -- It's recommended to leave version=false for now, since a lot the plugin that support versioninG,
    -- have outdated releases, which may break your Neovim install.
    version = false, -- always use the latest git commit
    -- version = "*", -- try installing the latest stable version for plugins that support semver
  },
  checker = { enabled = true }, -- automatically check for plugin updates
  performance = {
    rtp = {
      -- disable some rtp plugins
      disabled_plugins = {
        "gzip",
        -- "matchit",
        -- "matchparen",
        -- "netrwPlugin",
        "tarPlugin",
        "tohtml",
        "tutor",
        "zipPlugin",
      },
    },
  },
})
