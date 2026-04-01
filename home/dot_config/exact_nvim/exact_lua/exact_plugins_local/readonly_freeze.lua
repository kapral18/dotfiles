local fs_util = require("util.fs")

return {
  dir = fs_util.get_plugin_src_dir(),
  cmd = { "Freeze", "FreezeLine" },
  config = function()
    local freeze = require("plugins_local_src.freeze")

    vim.api.nvim_create_user_command("Freeze", function(opts)
      local line1 = opts.line1
      local line2 = opts.line2
      if opts.range == 0 then
        line1 = 1
        line2 = vim.api.nvim_buf_line_count(0)
      end
      freeze.freeze(line1, line2)
    end, { range = true, desc = "Screenshot code with freeze" })

    vim.api.nvim_create_user_command("FreezeLine", function()
      local line = vim.api.nvim_win_get_cursor(0)[1]
      freeze.freeze(line, line)
    end, { desc = "Screenshot current line with freeze" })
  end,
}
