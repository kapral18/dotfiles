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
        lsp_format = "fallback",
      }
      opts.formatters_by_ft = opts.formatters_by_ft or {}
      opts.formatters = vim.tbl_deep_extend("force", opts.formatters or {}, {
        injected = { options = { ignore_errors = true } },
      })
      return opts
    end,
    config = function(_, opts)
      require("conform").setup(opts)

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
