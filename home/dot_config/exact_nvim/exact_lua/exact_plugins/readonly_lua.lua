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
          root_dir = function(fname)
            local util = require("lspconfig").util
            local config_root =
              util.root_pattern(".luarc.json", ".luarc.jsonc", ".stylua.toml", "stylua.toml", "selene.toml")(fname)
            if config_root then
              return config_root
            end

            local git_root = util.root_pattern(".git")(fname)
            local chezmoi_src = vim.env.CHEZMOI_SOURCE_DIR
            if git_root and chezmoi_src and vim.startswith(git_root, chezmoi_src) then
              -- Avoid indexing the entire chezmoi source tree for single Lua files.
              return vim.fs.dirname(fname)
            end

            return git_root or vim.fs.dirname(fname)
          end,
          capabilities = {
            documentFormattingProvider = false,
            documentRangeFormattingProvider = false,
          },
          settings = {
            Lua = {
              workspace = {
                checkThirdParty = false,
                useGitIgnore = true,
                maxPreload = 1500,
                preloadFileSize = 200,
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
  },
}
