local fs_util = require("util.fs")

return {
  dir = fs_util.get_plugin_src_dir(),
  cmd = { "UnwrapMd" },
  config = function()
    local unwrap = require("plugins_local_src.unwrap-md")

    vim.api.nvim_create_user_command("UnwrapMd", function()
      unwrap.unwrap()
    end, { desc = "Unwrap hard-wrapped markdown lines" })
  end,
}
