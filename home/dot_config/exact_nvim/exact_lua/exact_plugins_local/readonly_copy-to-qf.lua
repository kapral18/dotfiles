local ctq = require("plugins_local_src.copy-to-qf")
local fs_util = require("util.fs")

vim.api.nvim_create_user_command("CopyBufferToQfDirs", function(opts)
  ctq.copy_buffer_to_quickfix_dirs(opts.args and opts.args == "force" and { force = true } or {})
end, { nargs = "?" })

return {
  dir = fs_util.get_plugin_src_dir(),
  keys = {
    {
      "<leader>cb",
      function()
        ctq.copy_buffer_to_quickfix_dirs()
      end,
      desc = "Copy current buffer to quickfix dirs",
    },
    {
      "<leader>cB",
      function()
        ctq.copy_buffer_to_quickfix_dirs({ force = true })
      end,
      desc = "Copy current buffer to quickfix dirs (forced)",
    },
  },
  cmd = "CopyBufferToQfDirs",
}
