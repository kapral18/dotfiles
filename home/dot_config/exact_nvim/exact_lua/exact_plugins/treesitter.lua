return {
  {
    "nvim-treesitter/nvim-treesitter",
    opts = {
      tree_setter = {
        enable = false,
      },
      textobjects = {
        select = {
          enable = true,
          lookahead = true,
          keymaps = {
            ["aa"] = "@parameter.outer",
            ["ia"] = "@parameter.inner",
            ["af"] = "@function.outer",
            ["if"] = "@function.inner",
            ["ac"] = "@class.outer",
            ["ic"] = "@class.inner",
            ["a/"] = "@comment.outer",
            ["i/"] = "@comment.inner",
            ["a?"] = "@conditional.outer",
            ["i?"] = "@conditional.inner",
            ["a:"] = "@loop.outer",
            ["i:"] = "@loop.inner",
            ["aj"] = "@jsx_attr",
            ["ij"] = "@jsx_attr",
          },
          include_surrounding_whitespace = true,
        },
        move = {
          enable = true,
          goto_next_start = { ["]r"] = "@return.outer" },
          goto_next_end = { ["]R"] = "@return.outer" },
          goto_previous_start = { ["[r"] = "@return.outer" },
          goto_previous_end = { ["[R"] = "@return.outer" },
        },
      },
    },
  },
  {
    "wellle/visual-split.vim",
  },
  {
    "aaronik/treewalker.nvim",
    lazy = false,

    -- The following options are the defaults.
    -- Treewalker aims for sane defaults, so these are each individually optional,
    -- and setup() does not need to be called, so the whole opts block is optional as well.
    opts = {
      -- Whether to briefly highlight the node after jumping to it
      highlight = true,

      -- How long should above highlight last (in ms)
      highlight_duration = 250,

      -- The color of the above highlight. Must be a valid vim highlight group.
      -- (see :h highlight-group for options)
      highlight_group = "CursorLine",
    },

    keys = {
      -- movement
      { "<A-S-k>", "<cmd>Treewalker Up<cr>", mode = { "n", "x" } },
      { "<A-S-j>", "<cmd>Treewalker Down<cr>", mode = { "n", "x" } },
      { "<A-S-l>", "<cmd>Treewalker Right<cr>", mode = { "n", "x" } },
      { "<A-S-h>", "<cmd>Treewalker Left<cr>", mode = { "n", "x" } },

      -- swapping
      { "<C-S-j>", "<cmd>Treewalker SwapDown<cr>" },
      { "<C-S-k>", "<cmd>Treewalker SwapUp<cr>" },
      { "<C-S-l>", "<cmd>Treewalker SwapRight<CR>" },
      { "<C-S-h>", "<cmd>Treewalker SwapLeft<CR>" },
    },
  },
  {
    "nmac427/guess-indent.nvim",
    opts = {},
  },
  {
    "echasnovski/mini.pairs",
    enabled = false,
  },
  {
    "junegunn/vim-easy-align",
    keys = {
      { "<leader>la", "<Plug>(EasyAlign)", mode = { "n", "x" }, desc = "Easy align" },
      { "<leader>lA", "<Plug>(LiveEasyAlign)", mode = { "n", "x" }, desc = "Live Easy align" },
    },
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
    lazy = false,
    config = function()
      require("nvim-ts-autotag").setup({
        opts = {
          enable_close_on_slash = true, -- Auto close on trailing </
        },
      })
    end,
  },
  {
    "echasnovski/mini.ai",
    enabled = false,
  },
}
