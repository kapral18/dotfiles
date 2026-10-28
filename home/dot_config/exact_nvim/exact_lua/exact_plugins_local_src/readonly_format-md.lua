local M = {}

function M.unwrap()
  local bufname = vim.api.nvim_buf_get_name(0)
  if bufname == "" then
    vim.notify(",format-md: buffer has no file", vim.log.levels.ERROR)
    return
  end

  vim.cmd("silent write")

  vim.system({ ",format-md", bufname }, { text = true }, function(result)
    vim.schedule(function()
      if result.code ~= 0 then
        vim.notify(",format-md failed: " .. (result.stderr or ""), vim.log.levels.ERROR)
        return
      end
      vim.cmd("silent edit")
      vim.notify(",format-md: finished " .. vim.fn.fnamemodify(bufname, ":t"))
    end)
  end)
end

return M
