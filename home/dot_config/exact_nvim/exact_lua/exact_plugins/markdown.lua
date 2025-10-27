vim.filetype.add({
  pattern = {
    [".*%.mdx"] = "markdown",
    ["README"] = "markdown",
  },
})

return {
  {
    "nvim-treesitter/nvim-treesitter",
    opts = function(_, opts)
      opts.ensure_installed = opts.ensure_installed or {}
      for _, lang in ipairs({ "markdown", "markdown_inline" }) do
        if not vim.tbl_contains(opts.ensure_installed, lang) then
          table.insert(opts.ensure_installed, lang)
        end
      end
    end,
  },
  {
    "mason-org/mason.nvim",
    opts = function(_, opts)
      opts.ensure_installed = opts.ensure_installed or {}
      for _, pkg in ipairs({ "marksman", "markdownlint" }) do
        if not vim.tbl_contains(opts.ensure_installed, pkg) then
          table.insert(opts.ensure_installed, pkg)
        end
      end
    end,
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
