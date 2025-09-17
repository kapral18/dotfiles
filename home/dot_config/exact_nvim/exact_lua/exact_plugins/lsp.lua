-- enabled if noice.nvim is off
vim.lsp.handlers["textDocument/hover"] = function(_, result, ctx, config)
  config = config or {}
  config.focus_id = ctx.method
  if not (result and result.contents) then
    return
  end
  local markdown_lines = vim.lsp.util.convert_input_to_markdown_lines(result.contents)
  markdown_lines = vim.split(table.concat(markdown_lines, "\n"), "\n", { trimempty = true })
  if vim.tbl_isempty(markdown_lines) then
    return
  end
  return vim.lsp.util.open_floating_preview(markdown_lines, "markdown", config)
end

return {
  {
    "neovim/nvim-lspconfig",
    opts = {
      inlay_hints = { enabled = false },
    },
  },
  {
    "kapral18/dim.lua",
    branch = "feat/add-new-ts-support",
    event = "LspAttach",
    opts = {
      disable_lsp_decorations = true,
    },
  },
}
