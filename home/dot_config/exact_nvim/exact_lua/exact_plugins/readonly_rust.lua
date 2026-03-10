return {
  {
    "nvim-treesitter/nvim-treesitter",
    opts = function(_, opts)
      opts.ensure_installed = vim.list_extend(opts.ensure_installed or {}, { "rust", "toml" })
      return opts
    end,
  },
  {
    "mason-org/mason.nvim",
    opts = function(_, opts)
      opts.ensure_installed = vim.list_extend(opts.ensure_installed or {}, { "codelldb", "taplo" })
      return opts
    end,
  },
  {
    "mrcjkb/rustaceanvim",
    version = "^4",
    ft = { "rust" },
    init = function()
      -- Configure rustaceanvim here
      vim.g.rustaceanvim = function()
        -- Get codelldb path from mason
        local adapter
        local mason_registry = require("mason-registry")
        if mason_registry.is_installed("codelldb") then
          local codelldb = mason_registry.get_package("codelldb")
          ---@diagnostic disable-next-line: undefined-field
          local extension_path = codelldb:get_install_path() .. "/extension/"
          local codelldb_path = extension_path .. "adapter/codelldb"
          local liblldb_path = extension_path .. "lldb/lib/liblldb.dylib" -- MacOS path
          adapter = require("rustaceanvim.config").get_codelldb_adapter(codelldb_path, liblldb_path)
        end

        return {
          dap = {
            adapter = adapter,
          },
          tools = {
            executor = require("rustaceanvim.executors").termopen,
            hover_actions = {
              auto_focus = true,
            },
          },
          server = {
            default_settings = {
              ["rust-analyzer"] = {
                cargo = {
                  allFeatures = true,
                },
                checkOnSave = {
                  command = "clippy",
                },
                completion = {
                  postfix = {
                    enable = true,
                  },
                },
              },
            },
          },
        }
      end
    end,
    keys = {
      {
        "<leader>tt",
        function()
          vim.cmd.RustLsp("testables")
        end,
        desc = "Run Rust test (testables)",
        ft = { "rust" },
      },
      {
        "<leader>td",
        function()
          vim.cmd.RustLsp("debuggables")
        end,
        desc = "Debug Rust test (debuggables)",
        ft = { "rust" },
      },
      {
        "<leader>tT",
        function()
          vim.cmd.RustLsp("runnables")
        end,
        desc = "Run Rust runnable",
        ft = { "rust" },
      },
      {
        "<leader>ca",
        function()
          vim.cmd.RustLsp("codeAction")
        end,
        desc = "Rust Code Action",
        ft = { "rust" },
      },
    },
  },
  {
    "neovim/nvim-lspconfig",
    opts = {
      servers = {
        rust_analyzer = {},
      },
    },
  },
  {
    "stevearc/conform.nvim",
    opts = function(_, opts)
      opts.formatters_by_ft = vim.tbl_deep_extend("force", opts.formatters_by_ft or {}, {
        rust = { "rustfmt" },
        toml = { "taplo" },
      })
      return opts
    end,
  },
}
