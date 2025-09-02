local config_path = vim.fn.stdpath("config")

local tme = require("plugins-local-src.ts-move-exports")

return {
  dir = config_path .. "/lua/plugins-local-src",
  keys = {
    {
      "<leader>]",
      function()
        tme.ts_move_exports()
      end,
      desc = "Move TS exports to new path",
      mode = "x",
    },
  },
}
