--- Formatting utilities
vim.g.autoformat = true

local M = {}

--- Registered formatters, sorted by priority (highest first)
---@type table[]
M._formatters = {}

--- Register a formatter descriptor
---@param formatter table {name, priority, primary, format(buf), sources(buf)}
function M.register(formatter)
  formatter.name = formatter.name or "formatter"
  if formatter.primary == nil then
    formatter.primary = true
  end
  formatter.priority = formatter.priority or 0
  table.insert(M._formatters, formatter)
  table.sort(M._formatters, function(a, b)
    return a.priority > b.priority
  end)
end

--- Format the current buffer
---@param opts? {force?: boolean, buf?: number}
function M.format(opts)
  opts = opts or {}
  local buf = opts.buf or vim.api.nvim_get_current_buf()

  if vim.g.autoformat == false and not opts.force then
    return
  end

  if not opts.force then
    local last_tick = vim.b[buf].format_changedtick
    if last_tick and last_tick == vim.api.nvim_buf_get_changedtick(buf) then
      return
    end
  end

  local have_primary = false
  for _, formatter in ipairs(M._formatters) do
    local sources = {}
    if type(formatter.sources) == "function" then
      local ok, result = pcall(formatter.sources, buf)
      if ok and type(result) == "table" then
        sources = result
      end
    end

    if #sources > 0 and not (formatter.primary and have_primary) then
      if formatter.primary then
        have_primary = true
      end
      local ok, err = pcall(formatter.format, buf)
      if not ok then
        vim.notify(("Formatter %s failed: %s"):format(formatter.name, err), vim.log.levels.ERROR)
      end
      if formatter.primary then
        break
      end
    end
  end

  vim.b[buf].format_changedtick = vim.api.nvim_buf_get_changedtick(buf)
end

--- Toggle autoformat via Snacks
---@param buf? boolean|number
---@return table
function M.snacks_toggle(buf)
  local snacks = require("snacks")

  if buf == true then
    buf = vim.api.nvim_get_current_buf()
  end
  if buf and not vim.api.nvim_buf_is_valid(buf) then
    buf = nil
  end

  return snacks.toggle({
    name = buf and "Buffer Autoformat" or "Autoformat",
    get = function()
      if buf and vim.api.nvim_buf_is_valid(buf) then
        return vim.b[buf].autoformat ~= false and vim.g.autoformat ~= false
      end
      return vim.g.autoformat ~= false
    end,
    set = function(state)
      if buf and vim.api.nvim_buf_is_valid(buf) then
        vim.b[buf].autoformat = state
      else
        vim.g.autoformat = state
      end
    end,
  })
end

--- Format expression for gq
function M.formatexpr()
  return vim.lsp.formatexpr({ timeout_ms = 3000 })
end

--- Get first available formatter from conform
---@param bufnr integer
---@param ... string
---@return string
function M.first(bufnr, ...)
  local conform = require("conform")
  for i = 1, select("#", ...) do
    local formatter = select(i, ...)
    if conform.get_formatter_info(formatter, bufnr).available then
      return formatter
    end
  end
  return select(1, ...)
end

return M
