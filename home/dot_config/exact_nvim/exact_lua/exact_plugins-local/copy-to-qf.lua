local config_path = vim.fn.stdpath("config")

local ctq = require("plugins-local-src.copy-to-qf")

vim.api.nvim_create_user_command("CopyBufferToQfDirs", function(opts)
  ctq.copy_buffer_to_quickfix_dirs(opts.args and opts.args == "force" and { force = true } or {})
end, { nargs = "?" })

return {
  dir = config_path .. "/lua/plugins-local-src",
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
