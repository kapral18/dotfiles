return {
  {
    "romainl/vim-qf",
    init = function()
      -- enable ack style mappings
      vim.g.qf_mapping_ack_style = 1
      -- disable auto quit if qf window is the only window
      vim.g.qf_auto_quit = 0
      -- if the path is too long, shorten each component to the first 3 chars
      vim.g.qf_shorten_path = 3
    end,
  },
}
