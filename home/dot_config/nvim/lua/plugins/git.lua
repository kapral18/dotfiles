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
    cond = function()
      return vim.loop.fs_stat(vim.loop.cwd() .. "/.git") or vim.fn.finddir(".git", ";") ~= ""
    end,
    keys = {
      { "<leader>gm", ":GitMessenger<CR>", desc = "Git Messenger" },
    },
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
    },
    keys = {
      { "<leader>gass", ":AdvancedGitSearch<CR>", desc = "AdvancedGitSearch", mode = { "n", "v" } },
      {
        "<leader>gasl",
        ":AdvancedGitSearch search_log_content<CR>",
        desc = "AGS Repo History Search",
        mode = { "n", "v" },
      },
      {
        "<leader>gasf",
        ":AdvancedGitSearch search_log_content_file<CR>",
        desc = "AGS File History Search",
        mode = { "n", "v" },
      },
      {
        "<leader>gasdf",
        ":AdvancedGitSearch diff_commit_file<CR>",
        desc = "AGS File vs commit",
        mode = { "n", "v" },
      },
      {
        "<leader>gasdl",
        ":AdvancedGitSearch diff_commit_line<CR>",
        desc = "AGS Line vs commit",
        mode = { "n", "v" },
      },
      {
        "<leader>gasdb",
        ":AdvancedGitSearch diff_branch_file<CR>",
        desc = "AGS Branch vs commit",
        mode = { "n", "v" },
      },
      {
        "<leader>gasr",
        ":AdvancedGitSearch checkout_reflog<CR>",
        desc = "AGS Checkout reflog",
        mode = { "n", "v" },
      },
      { "<leader>gasx", ":DiffviewClose<CR>", desc = "DiffviewClose", mode = { "n", "v" } },
    },
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
