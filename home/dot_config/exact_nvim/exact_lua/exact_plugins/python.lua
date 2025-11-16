vim.g.python_lsp = "basedpyright"
vim.g.python_ruff = vim.g.python_ruff or "ruff"

local python_lsp = vim.g.python_lsp or "pyright"
local python_ruff = vim.g.python_ruff or "ruff"

return {
  {
    "nvim-treesitter/nvim-treesitter",
    opts = function(_, opts)
      opts.ensure_installed = vim.list_extend(opts.ensure_installed or {}, { "python", "requirements" })
      return opts
    end,
  },
  {
    "neovim/nvim-lspconfig",
    opts = function(_, opts)
      opts.servers = opts.servers or {}
      opts.servers[python_lsp] = vim.tbl_deep_extend("force", {
        settings = {},
      }, opts.servers[python_lsp] or {})
      opts.servers[python_ruff] = vim.tbl_deep_extend("force", {
        keys = {
          {
            "<leader>co",
            function()
              vim.lsp.buf.code_action({
                context = {
                  only = { "source.organizeImports" },
                  diagnostics = {},
                },
              })
            end,
            desc = "Organize Imports",
          },
        },
      }, opts.servers[python_ruff] or {})

      opts.setup = opts.setup or {}
      local handler = opts.setup[python_ruff]
      opts.setup[python_ruff] = function(_, server_opts)
        if handler and handler(_, server_opts) then
          return true
        end
        require("snacks").util.lsp.on({ name = python_ruff }, function(_, client)
          client.server_capabilities.hoverProvider = false
        end)
      end

      for _, server in ipairs({ "pyright", "basedpyright", "ruff", "ruff_lsp" }) do
        if opts.servers[server] then
          opts.servers[server].enabled = server == python_lsp or server == python_ruff
        end
      end
    end,
  },
  {
    "mason-org/mason.nvim",
    opts = function(_, opts)
      opts.ensure_installed = vim.list_extend(opts.ensure_installed or {}, { "black", "isort", "ruff" })
      return opts
    end,
  },
  {
    "stevearc/conform.nvim",
    opts = function(_, opts)
      opts.formatters_by_ft = vim.tbl_deep_extend("force", opts.formatters_by_ft or {}, {
        python = { "isort", "black", stop_after_first = true },
      })
      return opts
    end,
  },
}
