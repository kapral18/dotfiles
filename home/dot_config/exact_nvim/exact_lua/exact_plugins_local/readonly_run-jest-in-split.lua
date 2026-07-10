local fs_util = require("util.fs")
local rjis = require("plugins_local_src.run-jest-in-split")
-- Note: the "q" close keymap is scoped per-buffer inside
-- util.terminal.run_in_split (only the Jest split's own terminal buffer),
-- not via a global TermOpen autocmd, so unrelated terminal buffers never
-- get rebound to the Jest close-all handler.

return {
  dir = fs_util.get_plugin_src_dir(),
  dependencies = { "nvim-lua/plenary.nvim" },
  keys = {
    {
      "<leader>tt",
      ft = { "javascript", "typescript", "javascriptreact", "typescriptreact", "tsx" },
      function()
        rjis.run_jest_in_split()
      end,
      desc = "Run Jest test in split",
    },
    {
      "<leader>td",
      ft = { "javascript", "typescript", "javascriptreact", "typescriptreact", "tsx" },
      function()
        rjis.run_jest_in_split({
          debug = true,
        })
      end,
      desc = "Debug Jest test in split",
    },
    {
      "<leader>tt",
      ft = { "lua" },
      function()
        require("plenary.test_harness").test_file(vim.fn.expand("%"))
      end,
      desc = "Run Lua test",
    },
    {
      "<leader>tT",
      ft = { "javascript", "typescript", "javascriptreact", "typescriptreact", "tsx" },
      function()
        rjis.run_jest_in_split({
          entire_file = true,
        })
      end,
      desc = "Run Jest file in split",
    },
    {
      "<leader>tD",
      ft = { "javascript", "typescript", "javascriptreact", "typescriptreact", "tsx" },
      function()
        rjis.run_jest_in_split({
          entire_file = true,
          debug = true,
        })
      end,
      desc = "Debug Jest file in split",
    },
    {
      "<leader>tu",
      ft = { "javascript", "typescript", "javascriptreact", "typescriptreact", "tsx" },
      function()
        rjis.run_jest_in_split({
          update_snapshots = true,
        })
      end,
      desc = "Run Jest test in split and update snapshots",
    },
    {
      "<leader>tU",
      ft = { "javascript", "typescript", "javascriptreact", "typescriptreact", "tsx" },
      function()
        rjis.run_jest_in_split({
          entire_file = true,
          update_snapshots = true,
        })
      end,
      desc = "Run Jest file in split and update snapshots",
    },
    {
      "<leader>tq",
      ft = { "javascript", "typescript", "javascriptreact", "typescriptreact", "tsx" },
      function()
        rjis.close_terminal_buffer()
      end,
      desc = "Close Jest terminal buffer",
    },
    {
      "<leader>tq",
      ft = { "lua" },
      function()
        require("plenary.test_harness").close_terminal_buffer()
      end,
      desc = "Close Lua test terminal buffer",
    },
  },
}
