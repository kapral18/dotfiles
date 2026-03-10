--- LSP utilities and helpers

local M = {}

--- LSP actions
M.action = {}

--- Source action
M.action.source = function()
  vim.lsp.buf.code_action({
    context = {
      only = { "source" },
      diagnostics = {},
    },
  })
end

--- Organize imports action getter
M.action["source.organizeImports"] = function()
  vim.lsp.buf.code_action({
    context = {
      only = { "source.organizeImports" },
      diagnostics = {},
    },
  })
end

--- LSP on attach utilities
M.on_attach = function(on_attach)
  vim.api.nvim_create_autocmd("LspAttach", {
    callback = function(args)
      local buffer = args.buf
      local client = vim.lsp.get_client_by_id(args.data.client_id)
      if client then
        on_attach(client, buffer)
      end
    end,
  })
end

--- Create an LSP formatter descriptor compatible with the format registry
---@param opts? {name?:string, filter?:string|table, primary?:boolean, priority?:number}
---@return table
function M.formatter(opts)
  opts = opts or {}
  local name = opts.name or "LSP"
  local filter = opts.filter
  local primary = opts.primary
  if primary == nil then
    primary = true
  end
  local priority = opts.priority or 10

  local function matches(client)
    if not filter then
      return true
    end
    if type(filter) == "string" then
      return client.name == filter
    end
    if type(filter) == "table" then
      if filter.name and client.name ~= filter.name then
        return false
      end
      if filter.id and client.id ~= filter.id then
        return false
      end
    end
    return true
  end

  local function list_clients(buf)
    local params = { bufnr = buf }
    if type(filter) == "table" then
      params = vim.tbl_extend("force", params, filter)
    elseif type(filter) == "string" then
      params.name = filter
    end
    return vim.lsp.get_clients(params)
  end

  return {
    name = name,
    primary = primary,
    priority = priority,
    format = function(buf)
      local params = { bufnr = buf, timeout_ms = 3000 }
      if type(filter) == "table" then
        params = vim.tbl_extend("force", params, filter)
      elseif type(filter) == "string" then
        params.filter = function(client)
          return client.name == filter
        end
      end
      vim.lsp.buf.format(params)
    end,
    sources = function(buf)
      local sources = {}
      for _, client in ipairs(list_clients(buf)) do
        local supports = client:supports_method("textDocument/formatting")
          or client:supports_method("textDocument/rangeFormatting")
        if supports and matches(client) then
          table.insert(sources, client.name)
        end
      end
      return sources
    end,
  }
end

return M
