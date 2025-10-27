--- Utility module that re-exports specialized submodules
--- This provides a unified entry point for all utility functions

local M = {}

-- Re-export submodules
M.format = require("util.format")
M.lsp = require("util.lsp")
M.pick = require("util.pick")
M.root = require("util.root")
M.cmp = require("util.cmp")
M.ui = require("util.ui")
M.treesitter = require("util.treesitter")
M.fzf = require("util.fzf")
M.fs = require("util.fs")

-- Re-export config from ui module
M.config = M.ui.config

-- Re-export commonly used functions for backwards compatibility
M.get_kind_filter = M.ui.get_kind_filter
M.kind_filter = M.ui.get_kind_filter
M.statuscolumn = M.ui.statuscolumn
M.lualine = M.ui.lualine

--- Check if a plugin is installed
---@param plugin string
---@return boolean
function M.has(plugin)
  return require("lazy.core.config").spec.plugins[plugin] ~= nil
end

--- Get opts for a plugin
---@param plugin string
---@return table
function M.opts(plugin)
  local lazy = require("lazy.core.config")
  local Plugin = require("lazy.core.plugin")
  return Plugin.values(lazy.plugins[plugin], "opts", false)
end

--- Execute function on lazy load
---@param plugin string
---@param fn fun()
function M.on_load(plugin, fn)
  local lazy = require("lazy.core.config")
  if lazy.plugins[plugin] and lazy.plugins[plugin]._.loaded then
    vim.schedule(fn)
  else
    vim.api.nvim_create_autocmd("User", {
      pattern = "LazyLoad",
      callback = function(event)
        if event.data == plugin then
          fn()
          return true
        end
      end,
    })
  end
end

--- Execute function on VeryLazy
---@param fn fun()
function M.on_very_lazy(fn)
  vim.api.nvim_create_autocmd("User", {
    pattern = "VeryLazy",
    callback = function()
      fn()
    end,
  })
end

--- Set buffer-local option with default value tracking
---@param option string
---@param value any
---@return boolean changed Returns true if the option was changed
function M.set_default(option, value)
  local current = vim.api.nvim_get_option_value(option, { scope = "local" })
  if current == nil or current == "" or current == 0 then
    vim.opt_local[option] = value
    return true
  end
  return false
end

--- Safe keymap set (doesn't override existing keymaps)
---@param mode string|string[]
---@param lhs string
---@param rhs string|function
---@param opts? table
function M.safe_keymap_set(mode, lhs, rhs, opts)
  opts = opts or {}
  -- Check if keymap already exists
  local modes = type(mode) == "table" and mode or { mode }
  for _, m in ipairs(modes) do
    local existing = vim.fn.maparg(lhs, m, false, true)
    if existing and existing.lhs ~= "" and not opts.force then
      return
    end
  end
  vim.keymap.set(mode, lhs, rhs, opts)
end

--- Notification utilities
function M.error(msg, opts)
  opts = opts or {}
  vim.notify(type(msg) == "table" and table.concat(msg, "\n") or msg, vim.log.levels.ERROR, opts)
end

function M.warn(msg, opts)
  opts = opts or {}
  vim.notify(type(msg) == "table" and table.concat(msg, "\n") or msg, vim.log.levels.WARN, opts)
end

function M.info(msg, opts)
  opts = opts or {}
  vim.notify(type(msg) == "table" and table.concat(msg, "\n") or msg, vim.log.levels.INFO, opts)
end

--- Plugin utilities
M.plugin = {}

--- Get index of an extra
---@param extra string
---@return number?
function M.plugin.extra_idx(extra) ---@diagnostic disable-line: unused-local
  -- This is a simplified version, would need proper tracking
  return nil
end

--- News/changelog (stub)
M.news = {}

function M.news.changelog()
  vim.notify("Changelog not available for this configuration", vim.log.levels.INFO)
end

--- Convenience functions and values forwarded from submodules
-- These are used throughout the config for backwards compatibility

-- File system utilities
M.get_plugin_src_dir = function() return M.fs.get_plugin_src_dir() end
M.get_git_root = function() return M.fs.get_git_root() end
M.get_project_root = function() return M.fs.get_project_root() end
M.glob_to_lua_pattern = function(glob) return M.fs.glob_to_lua_pattern(glob) end
M.file_exists = function(path) return M.fs.file_exists(path) end
M.safe_file_read = function(path) return M.fs.safe_file_read(path) end
M.safe_file_write = function(path, content, mode) return M.fs.safe_file_write(path, content, mode) end
M.normalize_path = function(path, base_dir) return M.fs.normalize_path(path, base_dir) end

-- FZF utilities
M.fzf_rg_opts = M.fzf.rg_opts
M.fzf_rg_opts_unrestricted = M.fzf.rg_opts_unrestricted
M.fzf_fd_opts_unrestricted = M.fzf.fd_opts_unrestricted
M.get_fzf_opts = function() return M.fzf.get_opts() end

-- Common utilities (from fzf module for backwards compatibility)
M.is_image = M.fzf.is_image
M.copy_to_clipboard = M.fzf.copy_to_clipboard
M.open_image = M.fzf.open_image

return M
