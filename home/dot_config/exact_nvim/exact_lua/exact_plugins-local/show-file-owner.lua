local config_path = vim.fn.stdpath("config")

local sfo = require("plugins-local-src.show-file-owner")

vim.api.nvim_create_user_command("ShowFileOwner", function()
  sfo.show_file_owner()
end, {
  desc = "Show the code owner of the current file",
})

return {
  {
    dir = config_path .. "/lua/plugins-local-src",
    keys = {
      {
        "<leader>0",
        function()
          sfo.show_file_owner()
        end,
        desc = "Show file code owner",
      },
    },
    cmd = { "ShowFileOwner" },
  },
}
