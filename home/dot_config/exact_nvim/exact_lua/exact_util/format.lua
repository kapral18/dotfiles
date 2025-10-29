--- Formatting utilities and unified format system
vim.g.autoformat = true

local M = {}

M._formatters = {}

local function sort_formatters()
  table.sort(M._formatters, function(a, b)
    local ap = a.priority or 0
    local bp = b.priority or 0
    return ap > bp
  end)
end

--- Register a formatter descriptor
---@param formatter table
function M.register(formatter)
  formatter = formatter or {}
  formatter.name = formatter.name or "formatter"
  if formatter.primary == nil then
    formatter.primary = true
  end
  if formatter.priority == nil then
    formatter.priority = 0
  end
  table.insert(M._formatters, formatter)
  sort_formatters()
end

--- Resolve registered formatters for a buffer
---@param buf? number
---@return table[]
function M.resolve(buf)
  buf = buf or vim.api.nvim_get_current_buf()
  local resolved = {}
  local have_primary = false

  for _, formatter in ipairs(M._formatters) do
    local sources = {}
    if type(formatter.sources) == "function" then
      local ok, result = pcall(formatter.sources, buf)
      if ok and type(result) == "table" then
        sources = result
      end
    end

    local active = #sources > 0
    if formatter.primary and have_primary then
      active = false
    end
    if active and formatter.primary then
      have_primary = true
    end

    table.insert(resolved, {
      formatter = formatter,
      sources = sources,
      active = active,
    })
  end

  return resolved
end

--- Format the current buffer or range
---@param opts? {force?: boolean, buf?: number}
function M.format(opts)
  opts = opts or {}
  local buf = opts.buf or vim.api.nvim_get_current_buf()

  if vim.g.autoformat == false and not opts.force then
    return
  end

  local used_registered = false
  for _, item in ipairs(M.resolve(buf)) do
    if item.active then
      used_registered = true
      local ok, err = pcall(item.formatter.format, buf)
      if not ok then
        vim.notify(("Formatter %s failed: %s"):format(item.formatter.name, err), vim.log.levels.ERROR)
      end
      if item.formatter.primary then
        break
      end
    end
  end

  if used_registered then
    return
  end

  -- Try conform.nvim first
  local have_conform, conform = pcall(require, "conform")
  if have_conform then
    conform.format(vim.tbl_extend("force", {
      timeout_ms = 3000,
      lsp_format = "fallback",
      buf = buf,
    }, opts))
  else
    vim.lsp.buf.format(vim.tbl_extend("force", {
      timeout_ms = 3000,
      buf = buf,
    }, opts))
  end
end

--- Toggle autoformat globally or per-buffer
---@param buf? boolean|number If true, uses current buffer. If number, uses that buffer. If nil/false, toggles globally.
---@return table
function M.snacks_toggle(buf)
  local ok, snacks = pcall(require, "snacks")
  if not ok then
    return {
      map = function()
        return function() end
      end,
    }
  end

  -- Convert true to current buffer number
  if buf == true then
    buf = vim.api.nvim_get_current_buf()
  end

  -- Validate buffer
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

--- Get first available formatter
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
