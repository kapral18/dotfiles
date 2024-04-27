return {
  {
    "nvim-treesitter/nvim-treesitter-context",
    enabled = false,
  },
  {
    "Wansmer/sibling-swap.nvim",
    dependencies = "nvim-treesitter/nvim-treesitter",
    opts = {
      use_default_keymaps = false,
      highlight_node_at_cursor = false,
    },
    keys = {
      {
        "<leader>.",
        function()
          -- swap with right and change operator in between
          require("sibling-swap").swap_with_right_with_opp()
        end,
        desc = "Move Node Right With Opp",
      },
      {
        "<leader>,",
        function()
          -- swap with right and change operator in between
          require("sibling-swap").swap_with_left_with_opp()
        end,
        desc = "Move Node Left With Opp",
      },
    },
  },
}
