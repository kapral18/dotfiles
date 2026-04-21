vim.filetype.add({
  pattern = {
    [".*%.mdx"] = "markdown",
    ["README"] = "markdown",
    ["SECURITY"] = "markdown",
    ["ARCHITECTURE"] = "markdown",
    ["TROUBLESHOOTING"] = "markdown",
    ["CONTRIBUTING"] = "markdown",
  },
})

return {
  {
    "nvim-treesitter/nvim-treesitter",
    opts = function(_, opts)
      opts.ensure_installed = vim.list_extend(opts.ensure_installed or {}, { "markdown", "markdown_inline" })
      return opts
    end,
  },
  {
    "mason-org/mason.nvim",
    opts = function(_, opts)
      opts.ensure_installed = vim.list_extend(opts.ensure_installed or {}, {
        "markdownlint",
        "prettierd",
        "prettier",
      })
      return opts
    end,
  },
  {
    "neovim/nvim-lspconfig",
    opts = {
      servers = {
        marksman = {},
      },
    },
  },
  {
    "stevearc/conform.nvim",
    opts = function(_, opts)
      -- Inherit built-in Prettier definitions but force proseWrap=preserve so
      -- project `proseWrap: "always"` (or printWidth reflow) does not rewrap
      -- markdown body text. Use `--prose-wrap=preserve` (one argv token) so
      -- prettierd's CLI parser does not treat a separate `preserve` as the path.
      local markdownlint_config = vim.fn.expand("~/.markdownlint.jsonc")
      opts.formatters = vim.tbl_deep_extend("force", opts.formatters or {}, {
        markdownlint_fix = {
          command = "markdownlint",
          args = { "--fix", "--config", markdownlint_config, "--", "$FILENAME" },
          stdin = false,
        },
        unwrap_md = {
          command = "unwrap-md",
          args = { "$FILENAME" },
          stdin = false,
        },
        prettier_markdown = {
          inherit = "prettier",
          prepend_args = { "--prose-wrap=preserve" },
        },
        prettierd_markdown = {
          inherit = "prettierd",
          prepend_args = { "--prose-wrap=preserve" },
        },
      })

      local md_formatters = function(bufnr)
        local conform = require("conform")
        local prettierd = conform.get_formatter_info("prettierd_markdown", bufnr)
        local prettier = prettierd.available and "prettierd_markdown" or "prettier_markdown"
        return { "markdownlint_fix", prettier }
      end
      local markdown_formatters = function(bufnr)
        local formatters = md_formatters(bufnr)
        table.insert(formatters, "unwrap_md")
        return formatters
      end
      opts.formatters_by_ft = vim.tbl_deep_extend("force", opts.formatters_by_ft or {}, {
        markdown = markdown_formatters,
        mdx = md_formatters,
      })
      return opts
    end,
  },
  {
    "mfussenegger/nvim-lint",
    opts = function(_, opts)
      opts.linters_by_ft = vim.tbl_deep_extend("force", opts.linters_by_ft or {}, {
        markdown = { "markdownlint" },
        mdx = { "markdownlint" },
      })
      opts.linters = vim.tbl_deep_extend("force", opts.linters or {}, {
        markdownlint = {
          prepend_args = { "--config", vim.fn.expand("~/.markdownlint.jsonc") },
        },
      })
      return opts
    end,
  },
  {
    "iamcco/markdown-preview.nvim",
    version = false,
    cmd = { "MarkdownPreviewToggle", "MarkdownPreview", "MarkdownPreviewStop" },
    build = function()
      pcall(vim.cmd.packadd, "markdown-preview.nvim")
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
