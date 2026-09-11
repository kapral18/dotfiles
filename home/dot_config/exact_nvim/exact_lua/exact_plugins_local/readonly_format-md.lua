local fs_util = require("util.fs")

return {
  dir = fs_util.get_plugin_src_dir(),
  cmd = { "FormatMd" },
  config = function()
    local unwrap = require("plugins_local_src.format-md")

    vim.api.nvim_create_user_command("FormatMd", function()
      unwrap.unwrap()
    end, { desc = "Normalize markdown prose wrapping" })
  end,
}
