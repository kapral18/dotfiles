--- Web toolchain detection helpers (Oxfmt/Biome/Prettier + OXlint detection)

local root = require("util.root")
local format = require("util.format")

local M = {}

---@param path string
---@return boolean
local function file_exists(path)
  return vim.uv.fs_stat(path) ~= nil
end

---@param dir string
---@param names string[]
---@return boolean
local function dir_has_any(dir, names)
  for _, name in ipairs(names) do
    if file_exists(dir .. "/" .. name) then
      return true
    end
  end
  return false
end

---@param bufnr integer
---@return boolean
function M.has_biome_config(bufnr)
  local dir = root.get(bufnr)
  return dir_has_any(dir, { "biome.json", "biome.jsonc" })
end

---@param bufnr integer
---@return boolean
function M.has_oxlint_config(bufnr)
  local dir = root.get(bufnr)
  return dir_has_any(dir, { ".oxlintrc.json", ".oxlintrc.jsonc", "oxlint.config.ts" })
end

---@param bufnr integer
---@return boolean
function M.has_oxfmt_config(bufnr)
  local dir = root.get(bufnr)
  return dir_has_any(dir, { ".oxfmtrc.json", ".oxfmtrc.jsonc", "oxfmt.config.ts" })
end

---@param bufnr integer
---@return string[]
function M.web_formatters(bufnr)
  -- Note: oxlint is a linter; its config does not imply oxfmt config.
  -- Only opt into oxfmt formatting when the repo declares oxfmt config.
  if M.has_oxfmt_config(bufnr) then
    if M.has_biome_config(bufnr) then
      return { format.first(bufnr, "oxfmt", "biome", "prettierd", "prettier") }
    end
    return { format.first(bufnr, "oxfmt", "prettierd", "prettier") }
  end

  if M.has_biome_config(bufnr) then
    return { format.first(bufnr, "biome", "prettierd", "prettier") }
  end
  return { format.first(bufnr, "prettierd", "prettier") }
end

return M
