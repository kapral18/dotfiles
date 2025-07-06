local config_path = vim.fn.stdpath("config")

local sst = require("plugins-local-src.switch-src-test")

return {
  dir = config_path .. "/lua/plugins-local-src",
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
