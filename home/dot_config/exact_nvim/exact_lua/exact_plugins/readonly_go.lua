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
    version = "*",
    dependencies = {
      { "ray-x/guihua.lua", version = false },
      "neovim/nvim-lspconfig",
      "nvim-treesitter/nvim-treesitter",
      { "leoluz/nvim-dap-go", version = false },
    },
    config = function()
      require("go").setup({
        lsp_cfg = false,
        dap_debug = true,
        test_runner = "go",
        run_in_floaterm = true,
        textobjects = false,
      })
      -- Configure nvim-dap-go as well for standard DAP setup
      require("dap-go").setup()

      -- go.nvim's `ftdetect/filetype.vim` ships
      --   au BufRead,BufNewFile *.tmpl set filetype=gotexttmpl
      -- which blanket-claims every `.tmpl` file. In this dotfiles repo
      -- `.tmpl` is chezmoi's template extension, handled per-source-dir by
      -- `alker0/chezmoi.vim` (ft like `gitconfig.chezmoitmpl`). When both
      -- autocmds fire on BufRead, the later one wins; go.nvim's registers
      -- lazily (CmdlineEnter), so after the first `:` keypress it starts
      -- winning and subsequent reloads show `gotexttmpl` plus the go.vim
      -- syntax's `goCharacter` matching on stray `'`s in comments/values.
      -- Drop the blanket rule; `.gotext`/`.gohtml` handlers remain, and
      -- real Go text templates can be opted into with `:setf gotexttmpl`.
      pcall(vim.api.nvim_clear_autocmds, {
        group = "filetypedetect",
        pattern = "*.tmpl",
      })

      -- Re-detect any already-open chezmoi template buffer that was stomped
      -- to `gotexttmpl` before this cleanup ran.
      local source_dir = vim.g["chezmoi#source_dir_path"]
      if type(source_dir) == "string" and source_dir ~= "" then
        for _, buf in ipairs(vim.api.nvim_list_bufs()) do
          if vim.api.nvim_buf_is_loaded(buf) and vim.bo[buf].filetype == "gotexttmpl" then
            local name = vim.api.nvim_buf_get_name(buf)
            if name:find(source_dir, 1, true) == 1 then
              vim.api.nvim_buf_call(buf, function()
                pcall(vim.cmd, "unlet! b:chezmoi_handling")
                pcall(vim.cmd, "unlet! b:chezmoi_detecting_fixed")
                pcall(vim.cmd, "doautocmd chezmoi_filetypedetect BufRead " .. vim.fn.fnameescape(name))
              end)
            end
          end
        end
      end
    end,
    keys = {
      {
        "<leader>tt",
        function()
          vim.cmd("GoTestFunc")
        end,
        desc = "Run Go test (func)",
        ft = { "go", "gomod" },
      },
      {
        "<leader>tT",
        function()
          vim.cmd("GoTestFile")
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
