local common_utils = require("utils.common")
local ctq = require("plugins-local-src.copy-to-qf")

vim.api.nvim_create_user_command("CopyBufferToQfDirs", function(opts)
  ctq.copy_buffer_to_quickfix_dirs(opts.args and opts.args == "force" and { force = true } or {})
end, { nargs = "?" })

return {
  dir = common_utils.get_plugin_src_dir(),
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
