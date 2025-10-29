return {
  {
    "stevearc/conform.nvim",
    dependencies = { "mason-org/mason.nvim" },
    lazy = false,
    cmd = "ConformInfo",
    keys = {
      {
        "<leader>cF",
        function()
          require("conform").format({ formatters = { "injected" }, timeout_ms = 3000 })
        end,
        mode = { "n", "x" },
        desc = "Format Injected Langs",
      },
    },
    opts = function(_, opts)
      opts.notify_on_error = false
      opts.default_format_opts = {
        timeout_ms = 3000,
        async = false,
        quiet = false,
        lsp_format = "never", -- LSP formatting is handled via format registry
      }
      opts.formatters_by_ft = opts.formatters_by_ft or {}
      opts.formatters = vim.tbl_deep_extend("force", opts.formatters or {}, {
        injected = { options = { ignore_errors = true } },
      })
      return opts
    end,
    config = function(_, opts)
      require("conform").setup(opts)

      -- Register conform as a formatter with higher priority than LSP
      require("util").format.register({
        name = "conform.nvim",
        primary = true,
        priority = 100, -- Higher than LSP (10), lower than eslint (200)
        sources = function(bufnr)
          local conform = require("conform")
          local formatters = conform.list_formatters_to_run(bufnr)
          local sources = {}
          for _, formatter in ipairs(formatters) do
            if formatter.available then
              table.insert(sources, formatter.name)
            end
          end
          return sources
        end,
        format = function(bufnr)
          require("conform").format({
            bufnr = bufnr,
            timeout_ms = 3000,
            lsp_format = "never", -- Don't use LSP here since it's handled separately
          })
        end,
      })

      -- Format on save via autocmd (not in opts)
      vim.api.nvim_create_autocmd("BufWritePre", {
        pattern = "*",
        callback = function(args)
          local disable_filetypes = { c = true, cpp = true }
          if disable_filetypes[vim.bo[args.buf].filetype] then
            return
          end
          require("util").format.format({ buf = args.buf })
        end,
      })
    end,
  },
}
