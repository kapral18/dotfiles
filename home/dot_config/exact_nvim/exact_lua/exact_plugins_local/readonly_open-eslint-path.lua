local fs_util = require("util.fs")
local oep = require("plugins_local_src.open-eslint-path")

return {
  dir = fs_util.get_plugin_src_dir(),
  keys = {
    {
      "<leader>sfe",
      function()
        oep.open_eslint_path()
      end,
      desc = "Open eslint path",
    },
  },
}
