local util = require("util")
local tme = require("plugins_local_src.ts-move-exports")

return {
  dir = util.get_plugin_src_dir(),
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
