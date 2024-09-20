local config_path = vim.fn.stdpath("config")

return {
  dir = config_path .. "/lua/plugins-local/show-file-owner",
  keys = {
    {
      "<leader>0",
      function()
        require("plugins-local.show-file-owner").show_file_owner()
      end,
      desc = "Show file code owner",
    },
  },
}
