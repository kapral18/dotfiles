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
    -- Try native vim.snippet first
    if vim.snippet then
      pcall(vim.snippet.stop)
    end
    -- Also try LuaSnip for backwards compatibility
    local has_luasnip, luasnip = pcall(require, "luasnip")
    if has_luasnip and luasnip.in_snippet() then
      luasnip.unlink_current()
    end
  end,
}

--- CMP confirm with snippet support
---@param opts? {select?: boolean, behavior?: any}
function M.confirm(opts)
  opts = opts or {}
  return function(fallback)
    local cmp = require("cmp")
    if cmp.visible() then
      cmp.confirm(opts)
    else
      fallback()
    end
  end
end

--- CMP expand snippet
---@param body string
function M.expand(body)
  local has_luasnip, luasnip = pcall(require, "luasnip")
  if has_luasnip then
    luasnip.lsp_expand(body)
    return
  end

  local has_snippets, snippets = pcall(require, "nvim-snippets")
  if has_snippets then
    snippets.expand(body)
    return
  end

  -- Fallback: just insert the body as-is
  vim.api.nvim_put({ body }, "", true, true)
end

--- CMP mapping helpers
---@param actions string[]
---@param fallback? string|fun()
function M.map(actions, fallback)
  return function()
    for _, name in ipairs(actions) do
      if M.actions[name] then
        local ret = M.actions[name]()
        if ret then
          return true
        end
      end
    end
    return type(fallback) == "function" and fallback() or fallback
  end
end

return M
