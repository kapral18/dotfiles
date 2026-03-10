local fs_util = require("util.fs")
local sst = require("plugins_local_src.switch-src-test")

return {
  dir = fs_util.get_plugin_src_dir(),
  keys = {
    {
      "<C-^>",
      function()
        sst.switch_src_test()
      end,
      desc = "Switch between source and test",
    },
  },
}
