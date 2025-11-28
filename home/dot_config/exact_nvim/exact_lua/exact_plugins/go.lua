return {
  {
    "nvim-treesitter/nvim-treesitter",
    opts = function(_, opts)
      opts.ensure_installed = vim.list_extend(opts.ensure_installed or {}, { "go", "gomod", "gosum", "gowork" })
      return opts
    end,
  },
  {
    "mason-org/mason.nvim",
    opts = function(_, opts)
      opts.ensure_installed = vim.list_extend(opts.ensure_installed or {}, {
        "delve",
        "golangci-lint",
        "goimports",
        "gofumpt",
        "gomodifytags",
        "impl",
        "gotests",
        "iferr",
      })
      return opts
    end,
  },
  {
    "ray-x/go.nvim",
    dependencies = {
      "ray-x/guihua.lua",
      "neovim/nvim-lspconfig",
      "nvim-treesitter/nvim-treesitter",
      "leoluz/nvim-dap-go",
    },
    config = function()
      require("go").setup({
        -- Disable auto-setup of LSP so it doesn't conflict with your existing nvim-lspconfig setup
        lsp_cfg = false,
        -- Enable DAP integration
        dap_debug = true,
        -- Test runner config
        test_runner = "go", -- or 'richgo', 'ginkgo', 'gotestsum'
        run_in_floaterm = true,
      })
      -- Configure nvim-dap-go as well for standard DAP setup
      require("dap-go").setup()
    end,
    keys = {
      {
        "<leader>tt",
        function()
          require("go.term").test_func()
        end,
        desc = "Run Go test (func)",
        ft = { "go", "gomod" },
      },
      {
        "<leader>tT",
        function()
          require("go.term").test_file()
        end,
        desc = "Run Go test (file)",
        ft = { "go", "gomod" },
      },
      {
        "<leader>td",
        function()
          require("dap-go").debug_test()
        end,
        desc = "Debug Go test (func)",
        ft = { "go", "gomod" },
      },
    },
    event = { "CmdlineEnter" },
    ft = { "go", "gomod" },
  },
  {
    "neovim/nvim-lspconfig",
    opts = function(_, opts)
      opts.servers = opts.servers or {}
      opts.servers.gopls = vim.tbl_deep_extend("force", {
        settings = {
          gopls = {
            gofumpt = true,
            usePlaceholders = true,
            completeUnimported = true,
            staticcheck = true,
            codelenses = {
              generate = true,
              run_govulncheck = true,
              test = true,
              tidy = true,
              upgrade_dependency = true,
              vendor = true,
            },
            analyses = {
              nilness = true,
              shadow = true,
              unusedparams = true,
              unusedwrite = true,
              useany = true,
            },
            hints = {
              assignVariableTypes = true,
              compositeLiteralFields = true,
              compositeLiteralTypes = true,
              constantValues = true,
              functionTypeParameters = true,
              parameterNames = true,
              rangeVariableTypes = true,
            },
          },
        },
      }, opts.servers.gopls or {})

      opts.setup = opts.setup or {}
      if not opts.setup.gopls then
        opts.setup.gopls = function(_, server_opts)
          require("snacks").util.lsp.on({ name = "gopls" }, function(_, client)
            if not client.server_capabilities.semanticTokensProvider then
              local semantic = client.config.capabilities.textDocument.semanticTokens
              client.server_capabilities.semanticTokensProvider = {
                full = true,
                legend = {
                  tokenTypes = semantic.tokenTypes,
                  tokenModifiers = semantic.tokenModifiers,
                },
                range = true,
              }
            end
          end)
        end
      end
    end,
  },
  {
    "stevearc/conform.nvim",
    opts = function(_, opts)
      opts.formatters_by_ft = vim.tbl_deep_extend("force", opts.formatters_by_ft or {}, {
        go = { "goimports", "gofumpt" },
      })
      return opts
    end,
  },
  {
    "mfussenegger/nvim-lint",
    optional = true,
    opts = function(_, opts)
      opts.linters_by_ft = vim.tbl_deep_extend("force", opts.linters_by_ft or {}, {
        go = { "golangci-lint" },
      })
      return opts
    end,
  },
  {
    "nvim-mini/mini.icons",
    opts = {
      file = {
        [".go-version"] = { glyph = "", hl = "MiniIconsBlue" },
      },
      filetype = {
        gotmpl = { glyph = "󰟓", hl = "MiniIconsGrey" },
      },
    },
  },
}
