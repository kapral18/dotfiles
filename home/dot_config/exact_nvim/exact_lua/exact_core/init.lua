local lazypath = vim.fn.stdpath("data") .. "/lazy/lazy.nvim"

if not vim.uv.fs_stat(lazypath) then
  vim.fn.system({
    "git",
    "clone",
    "--filter=blob:none",
    "https://github.com/folke/lazy.nvim.git",
    "--branch=stable",
    lazypath,
  })
end
vim.opt.rtp:prepend(lazypath)

require("core.options")

local plugin_modules = {
  "plugins.core",
  "plugins.colorscheme",
  "plugins.ai",
  "plugins.bash",
  "plugins.clangd",
  "plugins.bufferline",
  "plugins.chezmoi",
  "plugins.completion",
  "plugins.dap",
  "plugins.dashboard",
  "plugins.diff",
  "plugins.docker",
  "plugins.eslint",
  "plugins.fish",
  "plugins.fzf",
  "plugins.git",
  "plugins.github",
  "plugins.gx",
  "plugins.harper",
  "plugins.highlight",
  "plugins.hlargs",
  "plugins.html-css",
  "plugins.jinja",
  "plugins.jsonl",
  "plugins.k8s",
  "plugins.kdl",
  "plugins.lazydev",
  "plugins.leap",
  "plugins.live-command",
  "plugins.log",
  "plugins.formatting",
  "plugins.lsp",
  "plugins.lint",
  "plugins.lua",
  "plugins.lualine",
  "plugins.markdown",
  "plugins.marks",
  "plugins.strudel",
  "plugins.multi-cursors",
  "plugins.outline",
  "plugins.neo-tree",
  "plugins.inc-rename",
  "plugins.numb",
  "plugins.osv",
  "plugins.json",
  "plugins.go",
  "plugins.python",
  "plugins.rust",
  "plugins.search-and-replace",
  "plugins.session",
  "plugins.snacks",
  "plugins.notify",
  "plugins.telescope",
  "plugins.tmux",
  "plugins.tpope",
  "plugins.treesitter",
  "plugins.typescript-tools",
  "plugins.undo",
  "plugins.which-key",
  "plugins.xml",
  "plugins.yaml",
}

local local_modules = {
  "plugins_local.copy-to-qf",
  "plugins_local.fzf-filters-lsp",
  "plugins_local.owner-code-search",
  "plugins_local.qf",
  "plugins_local.run-jest-in-split",
  "plugins_local.save-ai-data",
  "plugins_local.show-file-owner",
  "plugins_local.summarize-commit",
  "plugins_local.switch-src-test",
  "plugins_local.toggle-win-width",
  "plugins_local.ts-move-exports",
  "plugins_local.winbar",
}

-- Build spec by importing each module individually
-- This allows easy batch disabling by commenting out ranges
local spec = {}

-- Add plugin modules
for _, module in ipairs(plugin_modules) do
  table.insert(spec, { import = module })
end

-- Add local plugin modules
for _, module in ipairs(local_modules) do
  table.insert(spec, { import = module })
end

require("lazy").setup(spec, {
  rocks = { hererocks = true },
  change_detection = { enabled = false, notify = false },
  concurrency = 100,
  defaults = {
    lazy = false,
    version = false,
  },
  checker = { enabled = true },
  performance = {
    rtp = {
      disabled_plugins = {
        "gzip",
        "tarPlugin",
        "tohtml",
        "tutor",
        "zipPlugin",
      },
    },
  },
})

require("core.autocmds")
require("core.keymaps")
