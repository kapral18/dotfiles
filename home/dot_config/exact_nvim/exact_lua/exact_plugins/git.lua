return {
  {
    "lewis6991/gitsigns.nvim",
    opts = {
      numhl = true, -- Toggle with `:Gitsigns toggle_numhl`
      linehl = false, -- Toggle with `:Gitsigns toggle_linehl`
      word_diff = false, -- Toggle with `:Gitsigns toggle_word_diff`
      current_line_blame = true, -- Toggle with `:Gitsigns toggle_current_line_blame`
      current_line_blame_opts = {
        virt_text = true,
        virt_text_pos = "eol", -- 'eol' | 'overlay' | 'right_align'
        delay = 500,
        attach_to_untracked = false,
      },
      current_line_blame_formatter = "<author>, <author_time> . <summary>",
    },
    keys = {
      { "<leader>ghtn", [[:Gitsigns toggle_numhl<CR>]], desc = "Toggle Num Highlight" },
      { "<leader>ghtl", [[:Gitsigns toggle_linehl<CR>]], desc = "Toggle Line Highlight" },
      { "<leader>ghtw", [[:Gitsigns toggle_word_diff<CR>]], desc = "Toggle Word Diff" },
      { "<leader>ghtb", [[:Gitsigns toggle_current_line_blame<CR>]], desc = "Toggle Blame Line" },
    },
  },
  -- git messages(commits, history, etc) under cursor
  {
    "rhysd/git-messenger.vim",
    cmd = { "GitMessenger" },
    dependencies = { "folke/which-key.nvim" },
    config = function()
      require("which-key").register({
        ["<leader>gm"] = { ":GitMessenger<CR>", "GitMessenger", mode = { "n", "v" } },
      })
    end,
    cond = function()
      return vim.loop.fs_stat(vim.loop.cwd() .. "/.git") or vim.fn.finddir(".git", ";") ~= ""
    end,
    init = function()
      vim.g.git_messenger_no_default_mappings = true
    end,
    event = "BufRead",
  },
  {
    "aaronhallaert/advanced-git-search.nvim",
    config = function()
      require("advanced_git_search.fzf").setup({
        diff_plugin = "diffview.nvim",
      })

      require("which-key").register({
        ["<leader>ga"] = {
          name = "Advanced Git Search",
          s = { ":AdvancedGitSearch<CR>", "AdvancedGitSearch", mode = { "n", "v" } },
          l = { ":AdvancedGitSearch search_log_content<CR>", "AGS Repo History Search", mode = { "n", "v" } },
          f = { ":AdvancedGitSearch search_log_content_file<CR>", "AGS File History Search", mode = { "n", "v" } },
          d = {
            name = "AdvancedGitSearch Diff",
            f = { ":AdvancedGitSearch diff_commit_file<CR>", "AGS File vs commit", mode = { "n", "v" } },
            l = { ":AdvancedGitSearch diff_commit_line<CR>", "AGS Line vs commit", mode = { "n", "v" } },
            b = { ":AdvancedGitSearch diff_branch_file<CR>", "AGS Branch vs commit", mode = { "n", "v" } },
          },
          r = { ":AdvancedGitSearch checkout_reflog<CR>", "AGS Checkout reflog", mode = { "n", "v" } },
          x = { ":DiffviewClose<CR>", "DiffviewClose", mode = { "n", "v" } },
        },
      })
    end,
    dependencies = {
      "ibhagwan/fzf-lua",
      -- to show diff splits and open commits in browser
      "tpope/vim-fugitive",
      -- to open commits in browser with fugitive
      "tpope/vim-rhubarb",
      -- optional: to replace the diff from fugitive with diffview.nvim
      -- (fugitive is still needed to open in browser)
      "sindrets/diffview.nvim", --- See dependencies
      "folke/which-key.nvim",
    },
  },
  {
    "ThePrimeagen/git-worktree.nvim",
    opts = {},
    dependencies = { "folke/which-key.nvim", "nvim-telescope/telescope.nvim" },
    config = function(_, opts)
      require("git-worktree").setup(opts)
      require("telescope").load_extension("git_worktree")
      require("which-key").register({
        ["<leader>gw"] = {
          name = "worktrees",
          m = { "<cmd>lua require('telescope').extensions.git_worktree.git_worktrees()<cr>", "Manage Worktrees" },
          c = { "<cmd>lua require('telescope').extensions.git_worktree.create_git_worktree()<cr>", "Create Worktree" },
        },
      })
    end,
  },
  {
    "nvim-treesitter/nvim-treesitter",
    opts = function(_, opts)
      if type(opts.ensure_installed) == "table" then
        vim.list_extend(opts.ensure_installed, {
          "git_config",
          "git_rebase",
          "gitattributes",
          "gitcommit",
          "gitignore",
        })
      end
    end,
  },
}
