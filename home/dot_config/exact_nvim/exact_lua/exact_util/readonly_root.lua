local M = {}

local lsp_ignore = { copilot = true }

---@param buf number?
---@return string
function M.get(buf)
  buf = buf or vim.api.nvim_get_current_buf()

  for _, client in ipairs(vim.lsp.get_clients({ bufnr = buf })) do
    if client.config.root_dir and not lsp_ignore[client.name] then
      return client.config.root_dir
    end
  end

  local root = vim.fs.root(buf, { ".git", "lua" })
  if root then
    return root
  end

  return vim.fn.getcwd()
end

---@return string
function M.git()
  local root = vim.fs.root(0, ".git")
  return root or vim.fn.getcwd()
end

return M
