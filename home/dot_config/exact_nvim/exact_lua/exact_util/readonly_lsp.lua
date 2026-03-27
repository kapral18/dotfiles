--- LSP utilities

local M = {}

--- Create an LSP formatter descriptor for the format registry
---@return table
function M.formatter()
  return {
    name = "LSP",
    primary = true,
    priority = 10,
    format = function(buf)
      vim.lsp.buf.format({ bufnr = buf, timeout_ms = 3000 })
    end,
    sources = function(buf)
      local sources = {}
      for _, client in ipairs(vim.lsp.get_clients({ bufnr = buf })) do
        if
          client:supports_method("textDocument/formatting")
          or client:supports_method("textDocument/rangeFormatting")
        then
          table.insert(sources, client.name)
        end
      end
      return sources
    end,
  }
end

return M
