local mini_ai_git_signs = function()
  local bufnr = vim.api.nvim_get_current_buf()
  local gitsigns_cache = require("gitsigns.cache").cache[bufnr]
  if not gitsigns_cache then
    return
  end
  local hunks = gitsigns_cache.hunks

  if not hunks then
    return
  end

  hunks = vim.tbl_map(function(hunk)
    local from_line = hunk.added.start
    local from_col = 1
    local to_line = hunk.vend
    local to_col = #vim.api.nvim_buf_get_lines(bufnr, to_line - 1, to_line, false)[1] + 1
    return {
      from = { line = from_line, col = from_col },
      to = { line = to_line, col = to_col },
    }
  end, hunks)

  return hunks
end

return {
  {
    "nvim-treesitter/nvim-treesitter",
    dependencies = {
      "RRethy/nvim-treesitter-endwise",
      "chrisgrieser/nvim-puppeteer",
    },
    opts = {
      endwise = {
        enable = true,
      },
      tree_setter = {
        enable = true,
      },
      textobjects = {
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
    "LunarWatcher/auto-pairs",
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
    event = "LazyFile",
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
    dependencies = {
      { "echasnovski/mini.extra", config = true },
    },
    event = "VeryLazy",
    opts = function(_, opts)
      local ai = require("mini.ai")
      local MiniExtra = require("mini.extra")
      return vim.tbl_deep_extend("force", opts, {
        custom_textobjects = {
          C = ai.gen_spec.treesitter({ a = "@comment.outer", i = "@comment.outer" }),
          D = MiniExtra.gen_ai_spec.diagnostic(),
          E = MiniExtra.gen_ai_spec.diagnostic({ severity = vim.diagnostic.severity.ERROR }),
          h = mini_ai_git_signs,
          j = ai.gen_spec.treesitter({
            a = { "@jsx_attr" },
            i = { "@jsx_attr" },
          }),
          k = ai.gen_spec.treesitter({
            i = { "@assignment.lhs", "@key.inner" },
            a = { "@assignment.outer", "@key.inner" },
          }),
          L = MiniExtra.gen_ai_spec.line(),
          N = MiniExtra.gen_ai_spec.number(),
          O = ai.gen_spec.treesitter({
            a = { "@function.outer", "@class.outer" },
            i = { "@function.inner", "@class.inner" },
          }),
          -- mixes up with leap-spooky so not using it
          -- r = ai.gen_spec.treesitter({ a = "@return.outer", i = "@return.inner" }),
          v = ai.gen_spec.treesitter({
            i = { "@assignment.rhs", "@value.inner", "@return.inner" },
            a = { "@assignment.outer", "@value.inner", "@return.outer" },
          }),
          ["$"] = ai.gen_spec.pair("$", "$", { type = "balanced" }),
        },
      })
    end,
  },
}
