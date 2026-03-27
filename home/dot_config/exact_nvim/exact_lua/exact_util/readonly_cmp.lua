--- Completion utilities

local M = {}

---@alias util.cmp.Action fun():boolean?
---@type table<string, util.cmp.Action>
M.actions = {
  -- Native Snippets
  snippet_forward = function()
    if vim.snippet and vim.snippet.active({ direction = 1 }) then
      vim.schedule(function()
        vim.snippet.jump(1)
      end)
      return true
    end
  end,
  snippet_stop = function()
    pcall(vim.snippet.stop)
  end,
}

return M
