return {
  {
    "nvim-telescope/telescope.nvim",
    keys = {
      {
        "<leader>fr",
        function()
          require("telescope.builtin").oldfiles({
            cwd = vim.uv.cwd(),
            only_cwd = true,
          })
        end,
        desc = "Recent",
      },
      {
        "<leader>fR",
        function()
          require("telescope.builtin").oldfiles()
        end,
        desc = "Recent (cwd)",
      },
    },
  },
}
