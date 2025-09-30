local common_utils = require("utils.common")
local sst = require("plugins-local-src.switch-src-test")

return {
  dir = common_utils.get_plugin_src_dir(),
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
