local config_path = vim.fn.stdpath("config")

return {
  dir = config_path .. "/lua/plugins-local",
  dependencies = { "nvim-lua/plenary.nvim" },
  keys = {
    {
      "<leader>tt",
      ft = { "javascript", "typescript", "javascriptreact", "typescriptreact", "tsx" },
      function()
        require("plugins-local.run-jest-in-split").run_jest_in_split()
      end,
      desc = "Run Jest test in split",
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
        require("plugins-local.run-jest-in-split").run_jest_in_split({
          entire_file = true,
        })
      end,
      desc = "Run Jest file in split",
    },
    {
      "<leader>tu",
      ft = { "javascript", "typescript", "javascriptreact", "typescriptreact", "tsx" },
      function()
        require("plugins-local.run-jest-in-split").run_jest_in_split({
          update_snapshots = true,
        })
      end,
      desc = "Run Jest test in split and update snapshots",
    },
    {
      "<leader>tU",
      ft = { "javascript", "typescript", "javascriptreact", "typescriptreact", "tsx" },
      function()
        require("plugins-local.run-jest-in-split").run_jest_in_split({
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
        require("plugins-local.run-jest-in-split").close_terminal_buffer()
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
  config = function()
    local run_jest_in_split = require("plugins-local.run-jest-in-split")
    -- Set up the keymap only for terminal buffers
    vim.api.nvim_create_autocmd("TermOpen", {
      pattern = "*",
      callback = function()
        vim.keymap.set(
          "n",
          "q",
          run_jest_in_split.close_terminal_buffer,
          { noremap = true, silent = true, buffer = true }
        )
      end,
    })
  end,
}
