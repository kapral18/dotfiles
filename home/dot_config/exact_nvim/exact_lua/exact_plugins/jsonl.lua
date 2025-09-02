return {
  {
    "kyoh86/vim-jsonl",
  },
  {
    "stevearc/conform.nvim",
    opts = {
      formatters = {
        jsonl = {
          command = "jq",
          args = { ".", "$FILENAME" },
        },
      },
      formatters_by_ft = {
        jsonl = { "jsonl" },
      },
    },
  },
}
