return {
  {
    "nvim-treesitter/nvim-treesitter",
    opts = { ensure_installed = { "astro", "css" } },
  },
  {
    "neovim/nvim-lspconfig",
    opts = {
      servers = {
        astro = {},
      },
    },
  },
  -- {
  --   "neovim/nvim-lspconfig",
  --   opts = function(_, opts)
  --     LazyVim.extend(opts.servers.vtsls, "settings.vtsls.tsserver.globalPlugins", {
  --       {
  --         name = "@astrojs/ts-plugin",
  --         location = LazyVim.get_pkg_path("astro-language-server", "/node_modules/@astrojs/ts-plugin"),
  --         enableForWorkspaceTypeScriptVersions = true,
  --       },
  --     })
  --   end,
  -- },
  {
    "stevearc/conform.nvim",
    opts = function(_, opts)
      opts.formatters_by_ft = opts.formatters_by_ft or {}
      opts.formatters_by_ft.astro = { "prettier" }
    end,
  },
}
