return {
  {
    "nvim-treesitter/nvim-treesitter",
    opts = { ensure_installed = { "astro" } },
  },
  {
    "neovim/nvim-lspconfig",
    opts = {
      servers = {
        astro = {},
      },
    },
    dependencies = {
      "typescript-tools.nvim",
      opts = function(_, opts)
        opts.settings = opts.settings or {}
        opts.settings.tsserver = opts.settings.tsserver or {}
        opts.settings.tsserver.plugins = opts.settings.tsserver.plugins or {}
        opts.settings.tsserver.plugins = vim.list_extend(opts.settings.tsserver.plugins, {
          vim.fn.stdpath("data") .. "/mason/packages/astro-language-server/node_modules/@astrojs/ts-plugin",
        })
      end,
    },
  },
  {
    "stevearc/conform.nvim",
    opts = function(_, opts)
      if LazyVim.has_extra("formatting.prettier") then
        opts.formatters_by_ft = opts.formatters_by_ft or {}
        opts.formatters_by_ft.astro = { "prettier" }
      end
    end,
  },
}
