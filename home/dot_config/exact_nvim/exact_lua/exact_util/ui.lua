--- UI utilities (icons, statuscolumn, lualine helpers)

local M = {}

---@class UtilConfig
---@field icons table Icon sets used throughout the config
M.config = {
  icons = {
    misc = {
      dots = "󰇘",
    },
    ft = {
      octo = "",
    },
    dap = {
      Stopped             = { "󰁕 ", "DiagnosticWarn", "DapStoppedLine" },
      Breakpoint          = " ",
      BreakpointCondition = " ",
      BreakpointRejected  = { " ", "DiagnosticError" },
      LogPoint            = ".>",
    },
    diagnostics = {
      Error = " ",
      Warn  = " ",
      Hint  = " ",
      Info  = " ",
    },
    git = {
      added = "▎",
      modified = "▎",
      removed = "",
    },
    kinds = {
      Array         = " ",
      Boolean       = "󰨙 ",
      Class         = " ",
      Codeium       = "󰘦 ",
      Color         = " ",
      Control       = " ",
      Collapsed     = " ",
      Constant      = "󰏿 ",
      Constructor   = " ",
      Copilot       = " ",
      Enum          = " ",
      EnumMember    = " ",
      Event         = " ",
      Field         = " ",
      File          = " ",
      Folder        = " ",
      Function      = "󰊕 ",
      Interface     = " ",
      Key           = " ",
      Keyword       = " ",
      Method        = "󰊕 ",
      Module        = " ",
      Namespace     = "󰦮 ",
      Null          = " ",
      Number        = "󰎠 ",
      Object        = " ",
      Operator      = " ",
      Package       = " ",
      Property      = " ",
      Reference     = " ",
      Snippet       = "󱄽 ",
      String        = " ",
      Struct        = "󰆼 ",
      Supermaven    = " ",
      TabNine       = "󰏚 ",
      Text          = " ",
      TypeParameter = " ",
      Unit          = " ",
      Value         = " ",
      Variable      = "󰀫 ",
    },
  },
}

--- Get symbol filter for document symbols
---@param bufnr number
---@return string[]|nil
function M.get_kind_filter(bufnr)
  bufnr = bufnr or vim.api.nvim_get_current_buf()
  local ft = vim.bo[bufnr].filetype
  if not ft then
    return nil
  end

  -- Default kind filter
  local default = {
    "Class",
    "Constructor",
    "Enum",
    "Field",
    "Function",
    "Interface",
    "Method",
    "Module",
    "Namespace",
    "Package",
    "Property",
    "Struct",
    "Trait",
  }

  -- Filetype-specific overrides
  local overrides = {
    markdown = false,
    help = false,
    lua = { "Class", "Constructor", "Enum", "Field", "Function", "Interface", "Module", "Namespace", "Property", "Struct", "Method" },
  }

  return overrides[ft] or default
end

--- Statuscolumn function
function M.statuscolumn()
  return ""
end

--- Lualine utilities
M.lualine = {}

--- Get pretty path for lualine
function M.lualine.pretty_path()
  return function()
    local path = vim.fn.expand("%:~:.")
    if path == "" then
      return "[No Name]"
    end

    local max_len = 40
    if #path > max_len then
      path = vim.fn.pathshorten(path)
    end

    return path
  end
end

--- Get root dir for lualine
---@param opts? table
function M.lualine.root_dir(opts)
  opts = opts or {}
  local icon = opts.icon or "󱉭"

  return {
    function()
      local root = require("util.root").get()
      local name = vim.fn.fnamemodify(root, ":t")
      return icon .. " " .. name
    end,
    cond = function()
      return true
    end,
  }
end

return M
