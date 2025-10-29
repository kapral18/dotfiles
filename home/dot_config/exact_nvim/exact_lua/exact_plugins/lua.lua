return {
  {
    "nvim-treesitter/nvim-treesitter",
    opts = function(_, opts)
      opts.ensure_installed = vim.list_extend(opts.ensure_installed or {}, { "lua", "luadoc", "luap" })
      return opts
    end,
  },
  {
    "mason-org/mason.nvim",
    opts = function(_, opts)
      opts.ensure_installed = vim.list_extend(opts.ensure_installed or {}, { "stylua" })
      return opts
    end,
  },
  {
    "neovim/nvim-lspconfig",
    dependencies = {
      "folke/lazydev.nvim", -- Ensure lazydev loads first
    },
    opts = {
      servers = {
        lua_ls = {
          settings = {
            Lua = {
              workspace = {
                checkThirdParty = false,
                library = {
                  string.format("%s/.hammerspoon/Spoons/EmmyLua.spoon/annotations", os.getenv("HOME")),
                },
              },
              completion = {
                callSnippet = "Replace",
              },
              runtime = {
                version = "LuaJIT",
              },
              hint = {
                enable = true,
                setType = true,
              },
              diagnostics = {
                globals = { "vim", "hs", "spoon" },
              },
              telemetry = {
                enable = false,
              },
            },
          },
        },
      },
    },
  },
  {
    "stevearc/conform.nvim",
    opts = function(_, opts)
      opts.formatters_by_ft = vim.tbl_deep_extend("force", opts.formatters_by_ft or {}, {
        lua = { "stylua" },
      })
      return opts
    end,
  },
}
