return {
  {
    "kapral18/bigfile.nvim",
    event = "BufReadPre",
    opts = {
      pattern = function(bufnr)
        local filename = vim.api.nvim_buf_get_name(bufnr)
        local filesize = vim.fn.getfsize(filename)

        if filename:match("package.json$") then
          return false
        else
          return filesize > 0.1 * 1024 * 1024 -- 0.1 MB
        end
      end,
    },
  },
}
