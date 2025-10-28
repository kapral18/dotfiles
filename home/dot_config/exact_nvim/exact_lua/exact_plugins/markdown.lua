vim.filetype.add({
  pattern = {
    [".*%.mdx"] = "markdown",
    ["README"] = "markdown",
  },
})

return {
  {
    "nvim-treesitter/nvim-treesitter",
    opts = {
      ensure_installed = { "markdown", "markdown_inline" },
    },
  },
  {
    "mason-org/mason.nvim",
    opts = {
      ensure_installed = { "marksman", "markdownlint" },
    },
  },
  {
    "neovim/nvim-lspconfig",
    opts = function(_, opts)
      opts.servers = opts.servers or {}
      opts.servers.marksman = vim.tbl_deep_extend("force", {}, opts.servers.marksman or {})
    end,
  },
  {
    "stevearc/conform.nvim",
    opts = function(_, opts)
      opts.formatters_by_ft = opts.formatters_by_ft or {}
      opts.formatters_by_ft.markdown = opts.formatters_by_ft.markdown or { "prettierd", "prettier" }
      opts.formatters_by_ft.mdx = opts.formatters_by_ft.mdx or { "prettierd", "prettier" }
    end,
  },
  {
    "mfussenegger/nvim-lint",
    opts = function(_, opts)
      opts.linters_by_ft = opts.linters_by_ft or {}
      opts.linters_by_ft.markdown = opts.linters_by_ft.markdown or { "markdownlint" }
    end,
  },
  {
    "iamcco/markdown-preview.nvim",
    cmd = { "MarkdownPreviewToggle", "MarkdownPreview", "MarkdownPreviewStop" },
    build = function()
      require("lazy").load({ plugins = { "markdown-preview.nvim" } })
      vim.fn["mkdp#util#install"]()
    end,
    ft = { "markdown", "mdx" },
    keys = {
      {
        "<leader>cp",
        "<cmd>MarkdownPreviewToggle<cr>",
        desc = "Markdown Preview",
        ft = "markdown",
      },
    },
  },
}
