local M = {}

function M.unwrap()
  local bufname = vim.api.nvim_buf_get_name(0)
  if bufname == "" then
    vim.notify("unwrap-md: buffer has no file", vim.log.levels.ERROR)
    return
  end

  -- Save before running so the script sees current content
  vim.cmd("silent write")

  vim.system({ "unwrap-md", bufname }, { text = true }, function(result)
    vim.schedule(function()
      if result.code ~= 0 then
        vim.notify("unwrap-md failed: " .. (result.stderr or ""), vim.log.levels.ERROR)
        return
      end
      -- Reload the buffer to pick up changes
      vim.cmd("silent edit")
      vim.notify("unwrap-md: unwrapped " .. vim.fn.fnamemodify(bufname, ":t"))
    end)
  end)
end

return M
