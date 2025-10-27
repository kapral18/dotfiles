local util = require("util")
local tww = require("plugins_local_src.toggle-win-width")

return {
  dir = util.get_plugin_src_dir(),
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
