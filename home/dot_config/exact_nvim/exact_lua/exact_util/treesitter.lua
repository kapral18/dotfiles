--- Treesitter utilities (for nvim-treesitter main branch)

local M = {}

M._installed = nil ---@type table<string,boolean>?
M._queries = {} ---@type table<string,boolean>

--- Get installed parsers
---@param update boolean?
---@return table<string,boolean>
function M.get_installed(update)
  if update then
    M._installed, M._queries = {}, {}
    local ok, parsers = pcall(function()
      return require("nvim-treesitter").get_installed("parsers")
    end)
    if ok and parsers then
      for _, lang in ipairs(parsers) do
        M._installed[lang] = true
      end
    end
  end
  return M._installed or {}
end

--- Check if query exists for language
---@param lang string
---@param query string
---@return boolean
function M.have_query(lang, query)
  local key = lang .. ":" .. query
  if M._queries[key] == nil then
    M._queries[key] = vim.treesitter.query.get(lang, query) ~= nil
  end
  return M._queries[key]
end

--- Check if treesitter parser is installed and optionally has query support
---@param what string|number|nil Buffer number or filetype
---@param query? string Query name to check
---@return boolean
function M.have(what, query)
  what = what or vim.api.nvim_get_current_buf()
  what = type(what) == "number" and vim.bo[what].filetype or what --[[@as string]]
  local lang = vim.treesitter.language.get_lang(what)
  if lang == nil or M.get_installed()[lang] == nil then
    return false
  end
  if query and not M.have_query(lang, query) then
    return false
  end
  return true
end

--- Treesitter fold expression
---@return string
function M.foldexpr()
  return M.have(nil, "folds") and vim.treesitter.foldexpr() or "0"
end

--- Treesitter indent expression
---@return number
function M.indentexpr()
  return M.have(nil, "indents") and require("nvim-treesitter").indentexpr() or -1
end

--- Build treesitter with callback
---@param cb function
function M.build(cb)
  M.ensure_treesitter_cli(function(ok, err)
    local health_ok, health = M.check()
    if health_ok then
      return cb()
    else
      local lines = { "Unmet requirements for nvim-treesitter:" }
      local keys = vim.tbl_keys(health) ---@type string[]
      table.sort(keys)
      for _, k in pairs(keys) do
        lines[#lines + 1] = ("- %s `%s`"):format(health[k] and "✅" or "❌", k)
      end
      vim.list_extend(lines, {
        "",
        "See: https://github.com/nvim-treesitter/nvim-treesitter/tree/main#requirements",
        "Run `:checkhealth nvim-treesitter` for more information.",
      })
      if err then
        vim.list_extend(lines, { "", err })
      end
      vim.notify(table.concat(lines, "\n"), vim.log.levels.ERROR, { title = "Treesitter" })
    end
  end)
end

--- Check system requirements for treesitter
---@return boolean ok, table<string,boolean> health
function M.check()
  local function have(tool)
    return vim.fn.executable(tool) == 1
  end

  local have_cc = vim.env.CC ~= nil or have("cc") or have("gcc") or have("clang")

  ---@type table<string,boolean>
  local ret = {
    ["tree-sitter (CLI)"] = have("tree-sitter"),
    ["C compiler"] = have_cc,
    tar = have("tar"),
    curl = have("curl"),
    node = have("node"),
  }
  
  local ok = true
  for _, v in pairs(ret) do
    ok = ok and v
  end
  return ok, ret
end

--- Ensure tree-sitter CLI is installed
---@param cb fun(ok:boolean, err?:string)
function M.ensure_treesitter_cli(cb)
  if vim.fn.executable("tree-sitter") == 1 then
    return cb(true)
  end

  -- Try installing with mason
  local mason_ok = pcall(require, "mason")
  if not mason_ok then
    return cb(false, "mason.nvim is not available")
  end

  -- Check again since we might have installed it already
  if vim.fn.executable("tree-sitter") == 1 then
    return cb(true)
  end

  local mr = require("mason-registry")
  mr.refresh(function()
    local p = mr.get_package("tree-sitter-cli")
    if not p:is_installed() then
      vim.notify("Installing tree-sitter-cli with mason.nvim...", vim.log.levels.INFO)
      p:install(
        nil,
        vim.schedule_wrap(function(success)
          if success then
            vim.notify("Installed tree-sitter-cli", vim.log.levels.INFO)
            cb(true)
          else
            cb(false, "Failed to install tree-sitter-cli")
          end
        end)
      )
    end
  end)
end

return M
