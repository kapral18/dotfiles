local config_path = vim.fn.stdpath("config")

return {
  dir = config_path .. "/lua/plugins-local",
  keys = {
    {
      "<leader>cb",
      function()
        require("plugins-local.copy-to-qf").copy_buffer_to_quickfix_dirs()
      end,
      desc = "Copy current buffer to quickfix dirs",
    },
    {
      "<leader>cB",
      function()
        require("plugins-local.copy-to-qf").copy_buffer_to_quickfix_dirs({ force = true })
      end,
      desc = "Copy current buffer to quickfix dirs (forced)",
    },
  },
  cmd = "CopyBufferToQfDirs",
  config = function()
    local copy_buffer_to_quickfix_dirs = require("plugins-local.copy-to-qf").copy_buffer_to_quickfix_dirs

    vim.api.nvim_create_user_command("CopyBufferToQfDirs", function(opts)
      copy_buffer_to_quickfix_dirs(opts.args and opts.args == "force" and { force = true } or {})
    end, { nargs = "?" })
  end,
}
