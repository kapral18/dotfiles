-- LSP Server to use for Python.
-- Set to "basedpyright" to use basedpyright instead of pyright.
vim.g.lazyvim_python_lsp = "basedpyright"

return {
  { "linux-cultist/venv-selector.nvim", enabled = false },
  {
    "nvim-treesitter/nvim-treesitter",
    opts = function(_, opts)
      if type(opts.ensure_installed) == "table" then
        vim.list_extend(opts.ensure_installed, { "requirements" })
      end
    end,
  },
  {
    "folke/which-key.nvim",
    opts = {
      spec = {
        { "<leader>p", group = " packages/dependencies" },
        { "<leader>pp", group = "python" },
      },
    },
  },
  {
    "mfussenegger/nvim-dap-python",
    enabled = false,
  },
}
