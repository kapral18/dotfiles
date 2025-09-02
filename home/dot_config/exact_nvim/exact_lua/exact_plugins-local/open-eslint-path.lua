local config_path = vim.fn.stdpath("config")

local oep = require("plugins-local-src.open-eslint-path")

return {
  dir = config_path .. "/lua/plugins-local-src",
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
