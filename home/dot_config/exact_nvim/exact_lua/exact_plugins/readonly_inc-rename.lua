return {
  {
    "smjonas/inc-rename.nvim",
    -- Load on LspAttach instead of cmd=IncRename: the packloader's deferred cmd
    -- stub re-runs via vim.cmd() and breaks inc-rename's command-preview handler
    -- (E32 / stale errmsg in the preview callback).
    event = "LspAttach",
    opts = {},
    config = function(_, opts)
      require("inc_rename").setup(opts)
    end,
  },

  -- LSP Keymaps
  {
    "neovim/nvim-lspconfig",
    opts = function(_, opts)
      opts.servers = opts.servers or {}
      opts.servers["*"] = opts.servers["*"] or {}
      opts.servers["*"].keys = opts.servers["*"].keys or {}

      table.insert(opts.servers["*"].keys, {
        "<leader>cr",
        function()
          local inc_rename = require("inc_rename")
          local cmd_name = (inc_rename.config and inc_rename.config.cmd_name) or "IncRename"
          return ":" .. cmd_name .. " " .. vim.fn.expand("<cword>")
        end,
        expr = true,
        desc = "Rename (inc-rename.nvim)",
        has = "rename",
      })

      return opts
    end,
  },
}
