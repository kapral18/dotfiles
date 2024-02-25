local constants = {
  disable_trim_whitespace = "disable_trim_whitespace",
  large_file_size = 1024 * 1024 * 5,
  treesitter_highlight_maxlines = 12 * 1024,
  treesitter_highlight_max_filesize = 200 * 1024, -- 200 KB
  treesitter_refactor_maxlines = 10 * 1024,
}

return {
  "nvim-treesitter/nvim-treesitter-refactor",
  lazy = true,
  dependencies = {
    "nvim-treesitter/nvim-treesitter",
    opts = function(_, opts)
      opts.refactor = {
        highlight_definitions = {
          enable = true,
          disable = function(_, bufnr)
            return vim.api.nvim_buf_line_count(bufnr) > constants.treesitter_refactor_maxlines
          end,
        },
      }
    end,
  },
}
