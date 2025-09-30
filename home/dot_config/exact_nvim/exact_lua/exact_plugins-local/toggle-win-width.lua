local common_utils = require("utils.common")
local tww = require("plugins-local-src.toggle-win-width")

return {
  dir = common_utils.get_plugin_src_dir(),
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
