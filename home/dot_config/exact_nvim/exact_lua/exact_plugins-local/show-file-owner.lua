local common_utils = require("utils.common")
local sfo = require("plugins-local-src.show-file-owner")

vim.api.nvim_create_user_command("ShowFileOwner", function()
  sfo.show_file_owner()
end, {
  desc = "Show the code owner of the current file",
})

return {
  {
    dir = common_utils.get_plugin_src_dir(),
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
