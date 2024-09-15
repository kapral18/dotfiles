local config_path = vim.fn.stdpath("config")

return {
  dir = config_path .. "/lua/plugins-local/ts-move-exports",
  keys = {
    {
      "<leader>aid",
      function()
        require("plugins-local.ts-move-exports").ts_move_exports()
      end,
      desc = "Move TS exports to new path",
    },
  },
}
