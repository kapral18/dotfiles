local config_path = vim.fn.stdpath("config")

return {
  dir = config_path .. "/lua/plugins-local",
  keys = {
    {
      "<C-^>",
      function()
        require("plugins-local.switch-src-test").switch_src_test()
      end,
      desc = "Switch between source and test",
    },
  },
}
