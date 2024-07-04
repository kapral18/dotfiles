return {
  "folke/edgy.nvim",
  event = "BufReadPost",
  init = function()
    vim.opt.laststatus = 3
    vim.opt.splitkeep = "screen"
  end,
  opts = {
    bottom = {
      {
        ft = "toggleterm",
        size = { height = 0.1 },
      },
      { ft = "qf", title = "QuickFix" },
      { ft = "dap-repl", title = " Debug REPL" },
      { ft = "dapui_console", size = { height = 0.1 }, title = "Debug Console" },
      "Trouble",
      "Noice",
      {
        ft = "help",
        size = { height = 20 },
        -- only show help buffers
        filter = function(buf)
          return vim.bo[buf].buftype == "help"
        end,
      },
      {
        ft = "NoiceHistory",
        title = " Log",
        open = function()
          require("noice").cmd("history")
        end,
      },
      {
        ft = "neotest-output-panel",
        title = " Test Output",
        open = function()
          vim.cmd.vsplit()
          require("neotest").output_panel.toggle()
        end,
      },
      {
        ft = "DiffviewFileHistory",
        title = " Diffs",
      },
    },
    left = {
      { ft = "undotree", title = "Undo Tree" },
      { ft = "dapui_scopes", title = " Scopes" },
      { ft = "dapui_watches", title = " Watches" },
      { ft = "dapui_breakpoints", title = " Breakpoints" },
      { ft = "dapui_stacks", title = " Stacks" },
      {
        ft = "diff",
        title = " Diffs",
      },

      {
        ft = "DiffviewFileHistory",
        title = " Diffs",
      },
      {
        ft = "DiffviewFiles",
        title = " Diffs",
      },
      {
        ft = "neotest-summary",
        title = "  Tests",
        open = function()
          require("neotest").summary.toggle()
        end,
      },
    },
    right = {
      "dapui_scopes",
      "sagaoutline",
      "neotest-output-panel",
      "neotest-summary",
    },
    options = {
      left = { size = 40 },
      bottom = { size = 10 },
      right = { size = 30 },
      top = { size = 10 },
    },
    wo = {
      winbar = true,
      signcolumn = "no",
    },
  },
}
