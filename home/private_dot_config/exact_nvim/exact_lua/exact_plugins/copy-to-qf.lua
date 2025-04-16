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
  },
  config = function()
    local copy_buffer_to_quickfix_dirs = require("plugins-local.copy-to-qf").copy_buffer_to_quickfix_dirs

    vim.api.nvim_create_user_command("CopyBufferToQfDirs", function(opts)
      copy_buffer_to_quickfix_dirs(opts.args)
    end, { nargs = "?" })
  end,
}
