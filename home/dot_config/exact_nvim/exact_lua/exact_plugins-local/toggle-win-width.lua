local config_path = vim.fn.stdpath("config")

local tww = require("plugins-local-src.toggle-win-width")

return {
  dir = config_path .. "/lua/plugins-local-src",
  keys = {
    {
      "<leader>=",
      function()
        tww.toggle_win_width()
      end,
      desc = "Toggle win width",
    },
  },
}
