local common_utils = require("utils.common")
local tme = require("plugins-local-src.ts-move-exports")

return {
  dir = common_utils.get_plugin_src_dir(),
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
