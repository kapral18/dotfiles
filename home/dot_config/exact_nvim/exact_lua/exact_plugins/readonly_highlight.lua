vim.hl = vim.hl or vim.highlight

return {
  {
    "tzachar/local-highlight.nvim",
    event = { "CursorHold", "CursorHoldI" },
    opts = {
      hlgroup = "LocalHighlight",
      cw_hlgroup = "LocalHighlight",
      debounce_timeout = 500,
      highlight_single_match = false,
      animate = {
        enabled = false,
      },
      disable_file_types = { "tex", "markdown" },
    },
    init = function()
      vim.api.nvim_create_autocmd("BufRead", {
        pattern = { "*.*" },
        callback = function(data)
          require("local-highlight").attach(data.buf)
        end,
      })
    end,
  },
  {
    "AlejandroSuero/freeze-code.nvim",
    opts = {
      copy = true,
      open = true,
      dir = vim.fn.expand("~/Downloads/screenshots"),
      freeze_config = { -- configuration options for `freeze` command
        output = "freeze.png",
        config = "base",
        theme = "pigments",
      },
    },
  },
}
