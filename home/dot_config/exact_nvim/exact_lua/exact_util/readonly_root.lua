--- Root detection utilities

vim.g.root_lsp_ignore = { "copilot" }

local M = {}

--- Detect root directory for the current buffer
---@param buf number?
---@return string
function M.get(buf)
  buf = buf or vim.api.nvim_get_current_buf()
  local root_patterns = vim.g.root_spec or { "lsp", { ".git", "lua" }, "cwd" }

  for _, pattern in ipairs(root_patterns) do
    if pattern == "lsp" then
      local clients = vim.lsp.get_clients({ bufnr = buf })
      for _, client in ipairs(clients) do
        if client.config.root_dir and vim.tbl_contains(vim.g.root_lsp_ignore or {}, client.name) == false then
          return client.config.root_dir
        end
      end
    elseif pattern == "cwd" then
      return vim.fn.getcwd()
    elseif type(pattern) == "table" then
      local root = vim.fs.root(buf, pattern)
      if root then
        return root
      end
    end
  end

  return vim.fn.getcwd()
end

--- Get git root directory
---@return string
function M.git()
  local root = vim.fs.root(0, ".git")
  return root or vim.fn.getcwd()
end

return M
