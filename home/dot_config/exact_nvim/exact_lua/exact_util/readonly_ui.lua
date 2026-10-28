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
      Stopped = { "󰁕 ", "DiagnosticWarn", "DapStoppedLine" },
      Breakpoint = " ",
      BreakpointCondition = " ",
      BreakpointRejected = { " ", "DiagnosticError" },
      LogPoint = ".>",
    },
    diagnostics = {
      Error = " ",
      Warn = " ",
      Hint = " ",
      Info = " ",
    },
    git = {
      added = "▎",
      modified = "▎",
      removed = "",
    },
    kinds = {
      Array = " ",
      Boolean = "󰨙 ",
      Class = " ",
      Codeium = "󰘦 ",
      Color = " ",
      Control = " ",
      Collapsed = " ",
      Constant = "󰏿 ",
      Constructor = " ",
      Copilot = " ",
      Enum = " ",
      EnumMember = " ",
      Event = " ",
      Field = " ",
      File = " ",
      Folder = " ",
      Function = "󰊕 ",
      Interface = " ",
      Key = " ",
      Keyword = " ",
      Method = "󰊕 ",
      Module = " ",
      Namespace = "󰦮 ",
      Null = " ",
      Number = "󰎠 ",
      Object = " ",
      Operator = " ",
      Package = " ",
      Property = " ",
      Reference = " ",
      Snippet = "󱄽 ",
      String = " ",
      Struct = "󰆼 ",
      Supermaven = " ",
      TabNine = "󰏚 ",
      Text = " ",
      TypeParameter = " ",
      Unit = " ",
      Value = " ",
      Variable = "󰀫 ",
    },
  },
}

M.lualine = {}

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
  }
end

return M
