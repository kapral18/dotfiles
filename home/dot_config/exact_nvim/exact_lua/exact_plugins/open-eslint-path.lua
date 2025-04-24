local config_path = vim.fn.stdpath("config")

return {
  dir = config_path .. "/lua/plugins-local",
  keys = {
    {
      "<leader>sfe",
      function()
        require("plugins-local.open-eslint-path").open_eslint_path()
      end,
      desc = "Open eslint path",
    },
  },
}
