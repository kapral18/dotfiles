return {
  { import = "lazyvim.plugins.extras.ui.treesitter-context" },
  {
    "nvim-treesitter/nvim-treesitter",
    dependencies = {
      "RRethy/nvim-treesitter-endwise",
      "chrisgrieser/nvim-puppeteer",
      "filNaj/tree-setter",
    },
    opts = {
      endwise = {
        enable = true,
      },
      tree_setter = {
        enable = true,
      },
    },
  },
  {
    "Wansmer/sibling-swap.nvim",
    dependencies = "nvim-treesitter/nvim-treesitter",
    opts = {
      use_default_keymaps = false,
      highlight_node_at_cursor = true,
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
  {
    "nmac427/guess-indent.nvim",
    opts = {},
  },
  {
    "echasnovski/mini.align",
    opts = {},
  },
  {
    "ckolkey/ts-node-action",
    dependencies = { "nvim-treesitter" },
    opts = {},
    keys = {
      { "<leader>j", "<cmd>NodeAction<cr>", mode = "n", desc = "Node action" },
    },
  },
  {
    "windwp/nvim-ts-autotag",
    event = "LazyFile",
    config = function()
      require("nvim-ts-autotag").setup({
        opts = {
          -- Defaults
          enable_close = true, -- Auto close tags
          enable_rename = true, -- Auto rename pairs of tags
          enable_close_on_slash = true, -- Auto close on trailing </
        },
      })
    end,
  },
}
