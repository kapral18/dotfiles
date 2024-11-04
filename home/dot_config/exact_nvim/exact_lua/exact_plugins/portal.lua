return {
  {
    "cbochs/portal.nvim",
    opts = {
      select_first = true,
    },
    keys = {
      {

        "<leader>pj",
        function()
          require("portal.builtin").jumplist.tunnel_backward({
            max_results = 10,
            filter = function(entry)
              -- is buffer included in currently open buffers
              return vim.api.nvim_buf_is_loaded(entry.buffer)
            end,
          })
        end,
        desc = "Open journal",
      },
      {
        "<leader>pk",
        function()
          require("portal.builtin").jumplist.tunnel_forward({
            max_results = 10,
            filter = function(entry)
              -- is buffer included in currently open buffers
              return vim.api.nvim_buf_is_loaded(entry.buffer)
            end,
          })
        end,
      },
    },
  },
}
