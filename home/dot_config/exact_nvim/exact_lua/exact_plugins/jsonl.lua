return {
  {
    "kyoh86/vim-jsonl",
  },
  {
    "stevearc/conform.nvim",
    opts = function(_, opts)
      opts.formatters = vim.tbl_deep_extend("force", opts.formatters or {}, {
        jq_jsonl = {
          command = "jq",
          args = { ".", "$FILENAME" },
        },
      })
      opts.formatters_by_ft = vim.tbl_deep_extend("force", opts.formatters_by_ft or {}, {
        jsonl = { "jq_jsonl" },
      })
      return opts
    end,
  },
}
