vim.hl = vim.hl or vim.highlight

return {
  {
    "tzachar/local-highlight.nvim",
    event = { "CursorHold", "CursorHoldI" },
    opts = {
      hlgroup = "LocalHighlight",
      cw_hlgroup = "LocalHighlight",
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
}
