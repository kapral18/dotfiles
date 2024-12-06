local config_path = vim.fn.stdpath("config")

return {
  dir = config_path .. "/lua/plugins-local",
  keys = {
    {
      "<leader>=",
      function()
        require("plugins-local.toggle-win-width").toggle_win_width()
      end,
      desc = "Toggle win width",
    },
  },
}
