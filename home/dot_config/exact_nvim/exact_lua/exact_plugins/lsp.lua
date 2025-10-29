local util = require("util")

-- enabled if noice.nvim is off
vim.lsp.handlers["textDocument/hover"] = function(_, result, ctx, config)
  config = config or {}
  config.focus_id = ctx.method
  if not (result and result.contents) then
    return
  end
  local markdown_lines = vim.lsp.util.convert_input_to_markdown_lines(result.contents)
  markdown_lines = vim.split(table.concat(markdown_lines, "\n"), "\n", { trimempty = true })
  if vim.tbl_isempty(markdown_lines) then
    return
  end
  return vim.lsp.util.open_floating_preview(markdown_lines, "markdown", config)
end

return {
  {
    "mason-org/mason.nvim",
    cmd = "Mason",
    event = "VeryLazy",
    build = ":MasonUpdate",
    opts = function(_, opts)
      opts.ensure_installed = opts.ensure_installed or {}
      return opts
    end,
    config = function(_, opts)
      require("mason").setup(opts)
      local registry = require("mason-registry")

      registry:on("package:install:success", function()
        vim.defer_fn(function()
          -- Trigger FileType event to reload LSP after package installation
          vim.cmd("doautocmd FileType")
        end, 100)
      end)

      local function ensure_installed()
        for _, name in ipairs(opts.ensure_installed or {}) do
          local ok, pkg = pcall(registry.get_package, name)
          if ok and not pkg:is_installed() then
            pkg:install()
          end
        end
      end

      if registry.refresh then
        registry.refresh(ensure_installed)
      else
        ensure_installed()
      end
    end,
  },
  {
    "mason-org/mason-lspconfig.nvim",
    dependencies = { "mason-org/mason.nvim" },
    opts = {
      ensure_installed = {},
    },
    config = function(_, opts)
      require("mason-lspconfig").setup(opts)
    end,
  },
  {
    "neovim/nvim-lspconfig",
    event = { "BufReadPre", "BufNewFile" },
    dependencies = {
      "hrsh7th/cmp-nvim-lsp",
      "mason-org/mason.nvim",
      "mason-org/mason-lspconfig.nvim",
    },
    opts = function(_, opts)
      opts = opts or {}

      -- Define base configuration
      local base = {
        inlay_hints = { enabled = false },
        diagnostics = {
          underline = true,
          update_in_insert = false,
          virtual_text = {
            spacing = 4,
            source = "if_many",
            prefix = "●",
            -- this will set set the prefix to a function that returns the diagnostics icon based on the severity
            -- prefix = "icons",
          },
          severity_sort = true,
          signs = {
            text = {
              [vim.diagnostic.severity.ERROR] = util.config.icons.diagnostics.Error,
              [vim.diagnostic.severity.WARN] = util.config.icons.diagnostics.Warn,
              [vim.diagnostic.severity.HINT] = util.config.icons.diagnostics.Hint,
              [vim.diagnostic.severity.INFO] = util.config.icons.diagnostics.Info,
            },
          },
          float = { border = "rounded" },
        },

        capabilities = {},
        servers = {
          ["*"] = {
            keys = {
              {
                "gd",
                function()
                  require("fzf-lua").lsp_definitions({ jump1 = true })
                end,
                desc = "Goto Definition",
                has = "definition",
              },
              {
                "gr",
                function()
                  require("fzf-lua").lsp_references({ jump1 = true })
                end,
                desc = "References",
                nowait = true,
              },
              {
                "gI",
                function()
                  require("fzf-lua").lsp_implementations({ jump1 = true })
                end,
                desc = "Goto Implementation",
              },
              {
                "gy",
                function()
                  require("fzf-lua").lsp_typedefs({ jump1 = true })
                end,
                desc = "Goto T[y]pe Definition",
              },
              {
                "gD",
                function()
                  require("fzf-lua").lsp_declarations({ jump1 = true })
                end,
                desc = "Goto Declaration",
              },
              { "K", vim.lsp.buf.hover, desc = "Hover" },
              { "gK", vim.lsp.buf.signature_help, desc = "Signature Help", has = "signatureHelp" },
              {
                "<c-k>",
                vim.lsp.buf.signature_help,
                mode = "i",
                desc = "Signature Help",
                has = "signatureHelp",
              },
              {
                "<leader>ca",
                vim.lsp.buf.code_action,
                desc = "Code Action",
                mode = { "n", "x" },
                has = "codeAction",
              },
              {
                "<leader>cA",
                function()
                  vim.lsp.buf.code_action({
                    context = {
                      only = { "source" },
                      diagnostics = {},
                    },
                  })
                end,
                desc = "Source Action",
                has = "codeAction",
              },
              {
                "<leader>ss",
                function()
                  require("fzf-lua").lsp_document_symbols()
                end,
                desc = "Document Symbols",
                has = "documentSymbol",
              },
              {
                "<leader>sS",
                function()
                  require("fzf-lua").lsp_live_workspace_symbols()
                end,
                desc = "Workspace Symbols",
                has = "workspaceSymbol",
              },
              {
                "<leader>cl",
                function()
                  require("snacks").picker.lsp_config()
                end,
                desc = "Lsp Info",
              },
            },
          },
        },
        setup = {},
      }
      -- Deep merge base with incoming opts
      opts = vim.tbl_deep_extend("force", base, opts)
      return opts
    end,
    config = function(_, opts)
      vim.diagnostic.config(opts.diagnostics or {})

      -- Register LSP formatting
      util.format.register(util.lsp.formatter())

      -- Setup LSP keymaps using Snacks (LazyVim approach)
      for server, server_opts in pairs(opts.servers) do
        if type(server_opts) == "table" and server_opts.keys then
          local Keys = require("lazy.core.handler.keys")
          local filter = { name = server ~= "*" and server or nil }

          for _, keys in pairs(Keys.resolve(server_opts.keys)) do
            local filters = {} ---@type vim.lsp.get_clients.Filter[]
            if keys.has then
              local methods = type(keys.has) == "string" and { keys.has } or keys.has
              for _, method in ipairs(methods) do
                method = method:find("/") and method or ("textDocument/" .. method)
                filters[#filters + 1] = vim.tbl_extend("force", vim.deepcopy(filter), { method = method })
              end
            else
              filters[#filters + 1] = filter
            end

            for _, f in ipairs(filters) do
              local opts_local = Keys.opts(keys)
              opts_local.lsp = f
              opts_local.enabled = keys.enabled
              require("snacks").keymap.set(keys.mode or "n", keys.lhs, keys.rhs, opts_local)
            end
          end
        end
      end

      -- Delete native Neovim 0.11 LSP mappings that conflict with our custom ones
      -- Native mappings: grr (references), gri (implementation), grt (type_definition), gra (code_action), grn (rename)
      vim.api.nvim_create_autocmd("LspAttach", {
        callback = function()
          pcall(vim.keymap.del, "n", "grr")
          pcall(vim.keymap.del, "n", "gri")
          pcall(vim.keymap.del, "n", "grt")
          pcall(vim.keymap.del, "n", "gra")
          pcall(vim.keymap.del, "n", "grn")
        end,
      })

      local capabilities =
        vim.tbl_deep_extend("force", {}, vim.lsp.protocol.make_client_capabilities(), opts.capabilities or {})

      local cmp_ok, cmp_nvim_lsp = pcall(require, "cmp_nvim_lsp")
      if cmp_ok then
        capabilities = cmp_nvim_lsp.default_capabilities(capabilities)
      end

      -- Get all servers available through mason-lspconfig
      local have_mason = pcall(require, "mason-lspconfig")
      local mason_all = have_mason
          and vim.tbl_keys(require("mason-lspconfig.mappings").get_mason_map().lspconfig_to_package)
        or {}
      local mason_exclude = {}

      ---@return boolean? use_mason
      local function configure(server)
        if server == "*" then
          return false
        end

        local server_opts = opts.servers[server]
        server_opts = server_opts == true and {} or (not server_opts) and { enabled = false } or server_opts

        if server_opts.enabled == false then
          mason_exclude[#mason_exclude + 1] = server
          return
        end

        server_opts = vim.tbl_deep_extend(
          "force",
          {
            capabilities = vim.deepcopy(capabilities),
          },
          server_opts or {},
          {
            inlay_hints = opts.inlay_hints,
          }
        )

        local use_mason = server_opts.mason ~= false and vim.tbl_contains(mason_all, server)
        local setup = opts.setup[server] or opts.setup["*"]
        if setup and setup(server, server_opts) then
          mason_exclude[#mason_exclude + 1] = server
        else
          vim.lsp.config(server, server_opts)
          if not use_mason then
            vim.lsp.enable(server)
          end
        end
        return use_mason
      end

      local install = vim.tbl_filter(configure, vim.tbl_keys(opts.servers))
      if have_mason then
        require("mason-lspconfig").setup({
          ensure_installed = install,
          handlers = {
            function(server)
              vim.lsp.enable(server)
            end,
          },
        })
      end
    end,
  },
  {
    "kapral18/dim.lua",
    branch = "feat/add-new-ts-support",
    event = "LspAttach",
    opts = {
      disable_lsp_decorations = true,
    },
  },
}
