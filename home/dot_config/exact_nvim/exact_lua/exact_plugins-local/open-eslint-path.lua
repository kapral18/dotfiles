local common_utils = require("utils.common")
local oep = require("plugins-local-src.open-eslint-path")

return {
  dir = common_utils.get_plugin_src_dir(),
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
