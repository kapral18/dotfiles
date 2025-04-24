-- enabled if noice.nvim is off
vim.lsp.handlers["textDocument/hover"] = function(_, result, ctx, config)
  config = config or {}
  config.focus_id = ctx.method
  if not (result and result.contents) then
    return
  end
  local markdown_lines = vim.lsp.util.convert_input_to_markdown_lines(result.contents)
  markdown_lines = vim.lsp.util.trim_empty_lines(markdown_lines)
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
    "aznhe21/actions-preview.nvim",
    event = "LspAttach",
    dependencies = {
      {
        "neovim/nvim-lspconfig",
        opts = function()
          local keys = require("lazyvim.plugins.lsp.keymaps").get()

          keys[#keys + 1] = { "<leader>ca", false }
        end,
      },
    },
    opts = {
      backend = { "nui" },
      diff = {
        algorithm = "patience",
        ignore_whitespace = true,
      },
    },
    keys = {
      {
        "<leader>ca",
        function()
          require("actions-preview").code_actions()
        end,
        mode = { "n", "v" },
        desc = "Code Action Preview",
      },
    },
  },
  {
    "0oAstro/dim.lua",
    event = "LspAttach",
    opts = {
      disable_lsp_decorations = true,
    },
  },
}
