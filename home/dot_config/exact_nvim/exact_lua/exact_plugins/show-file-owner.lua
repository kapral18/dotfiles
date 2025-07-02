local config_path = vim.fn.stdpath("config")

return {
  {
    dir = config_path .. "/lua/plugins-local",
    keys = {
      {
        "<leader>0",
        function()
          require("plugins-local.show-file-owner").show_file_owner()
        end,
        desc = "Show file code owner",
      },
    },
    cmd = { "ShowFileOwner" },
    config = function()
      local show_file_owner = require("plugins-local.show-file-owner").show_file_owner

      vim.api.nvim_create_user_command("ShowFileOwner", function()
        show_file_owner()
      end, {
        desc = "Show the code owner of the current file",
      })
    end,
  },
}
