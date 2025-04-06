-- LSP Server to use for Python.
-- Set to "basedpyright" to use basedpyright instead of pyright.
vim.g.lazyvim_python_lsp = "basedpyright"

return {
  {
    "nvim-treesitter/nvim-treesitter",
    opts = function(_, opts)
      if type(opts.ensure_installed) == "table" then
        vim.list_extend(opts.ensure_installed, { "requirements" })
      end
    end,
  },
  {
    "MeanderingProgrammer/py-requirements.nvim",
    event = {
      "BufRead requirements.txt",
    },
    dependencies = {
      { "nvim-lua/plenary.nvim" },
      {
        "hrsh7th/nvim-cmp",
        dependencies = {},
        opts = function(_, opts)
          table.insert(opts.sources, { name = "py-requirements" })
        end,
      },
    },
    opts = {},
    -- stylua: ignore start
    keys = {
      { "<leader>ppu", function() require("py-requirements").upgrade() end, desc = "Update Package" },
      { "<leader>ppi", function() require("py-requirements").show_description() end, desc = "Package Info" },
      { "<leader>ppa", function() require("py-requirements").upgrade_all() end, desc = "Update All Packages" },
    },
    -- stylua: ignore end
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
}
