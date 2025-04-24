local selected_colorscheme = "melange"

local function apply_highlight_overwrites()
  if vim.g.colors == "melange" then
    vim.api.nvim_set_hl(0, "Type", { fg = "lightblue" })
    vim.api.nvim_set_hl(0, "@lsp.type.namespace", { fg = "azure" })
  end
end

-- Set up autocommand for VimEnter event
vim.api.nvim_create_autocmd("VimEnter", {
  callback = function()
    -- Schedule the highlight application to occur after all plugins have initialized
    vim.schedule(function()
      apply_highlight_overwrites()

      vim.api.nvim_create_augroup("k18.colorscheme", {})

      -- Set up autocommand for subsequent colorscheme changes
      vim.api.nvim_create_autocmd("ColorScheme", {
        pattern = "*",
        group = "k18.colorscheme",
        callback = apply_highlight_overwrites,
      })
    end)
  end,
})

return {
  { "savq/melange-nvim" },
  { "LazyVim/LazyVim", opts = { colorscheme = selected_colorscheme } },
}
