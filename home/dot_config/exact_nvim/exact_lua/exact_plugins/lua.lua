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
          capabilities = {
            documentFormattingProvider = false,
            documentRangeFormattingProvider = false,
          },
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
                enable = false,
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
    init = function()
      vim.api.nvim_create_autocmd("FileType", {
        pattern = "lua",
        once = true,
        callback = function()
          require("util").format.register({
            name = "lua.stylua",
            primary = true,
            priority = 150, -- Higher than default conform (100)
            sources = function(bufnr)
              if vim.bo[bufnr].filetype == "lua" then
                return { "stylua" }
              end
              return {}
            end,
            format = function(bufnr)
              require("conform").format({
                bufnr = bufnr,
                timeout_ms = 10000,
                async = false,
                lsp_format = "never",
              })
            end,
          })
        end,
      })
    end,
  },
}
