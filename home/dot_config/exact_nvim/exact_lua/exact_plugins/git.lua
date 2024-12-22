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
      update_debounce = 1000,
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
      require("which-key").add({
        { "<leader>gm", ":GitMessenger<CR>", desc = "GitMessenger", mode = { "n", "v" } },
      })
    end,
    cond = function()
      return vim.uv.fs_stat(vim.uv.cwd() .. "/.git") or vim.fn.finddir(".git", ";") ~= ""
    end,
    init = function()
      vim.g.git_messenger_no_default_mappings = true
      vim.g.git_messenger_always_into_popup = true
      vim.g.git_messenger_extra_blame_args = "-w"
      vim.g.git_messenger_floating_win_opts = { border = "single" }
      vim.g.git_messenger_popup_content_margins = false
      vim.g.git_messenger_include_diff = "current"
    end,
    event = "BufRead",
  },
  {
    "aaronhallaert/advanced-git-search.nvim",
    cmd = { "AdvancedGitSearch" },
    keys = {
      { "<leader>gas", ":AdvancedGitSearch<CR>", desc = "AdvancedGitSearch" },
      { "<leader>gal", ":AdvancedGitSearch search_log_content<CR>", desc = "AGS Repo History Search" },
      { "<leader>gaf", ":AdvancedGitSearch search_log_content_file<CR>", desc = "AGS File History Search" },
      { "<leader>gadf", ":AdvancedGitSearch diff_commit_file<CR>", desc = "AGS File vs commit" },
      { "<leader>gadl", ":AdvancedGitSearch diff_commit_line<CR>", desc = "AGS Line vs commit" },
      { "<leader>gadb", ":AdvancedGitSearch diff_branch_file<CR>", desc = "AGS Branch vs commit" },
      { "<leader>gar", ":AdvancedGitSearch checkout_reflog<CR>", desc = "AGS Checkout reflog" },
    },
    config = function()
      -- optional: setup telescope before loading the extension
      require("telescope").setup({
        -- move this to the place where you call the telescope setup function
        extensions = {
          advanced_git_search = {
            diff_plugin = "diffview.nvim",
          },
        },
      })

      require("telescope").load_extension("advanced_git_search")

      require("which-key").add({
        { "<leader>ga", group = "Advanced Git Search", mode = { "n", "v" } },
        { "<leader>gad", group = "AdvancedGitSearch Diff" },
      })
    end,
    dependencies = {
      "nvim-telescope/telescope.nvim",
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
  { "tpope/vim-fugitive" },
  {
    "sindrets/diffview.nvim",
    config = true,
    keys = {

      { "<leader>dfx", ":DiffviewClose<CR>", desc = "DiffviewClose" },
    },
  },
}
