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
      update_debounce = 500,
      diff_opts = {
        algorithm = "histogram",
        vertical = true,
      },
    },
    keys = {
      { "<leader>ghP", [[:Gitsigns preview_hunk<CR>]], desc = "Preview Hunk" },
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
  {
    "sindrets/diffview.nvim",
    lazy = false,
    config = true,
    keys = {
      { "<leader>dfx", "<CMD>DiffviewClose<CR>", desc = "DiffviewClose" },
      { "<leader>dfh", ":DiffviewFileHistory --follow<CR>", desc = "DiffviewFileHistory", mode = { "n", "x" } },
      { "<leader>dfe", "<CMD>DiffviewToggleFiles<CR>", desc = "DiffviewToggleFiles" },
      { "<leader>dfo", "<CMD>DiffviewOpen<CR>", desc = "DiffviewOpen" },
      { "q", ":DiffviewClose<CR>", desc = "DiffviewClose", ft = { "DiffviewFiles", "DiffviewFileHistory" } },
    },
  },
  {
    "rbong/vim-flog",
    lazy = true,
    cmd = { "Flog", "Flogsplit", "Floggit" },
    dependencies = {
      "tpope/vim-fugitive",
    },
  },
  {
    "FabijanZulj/blame.nvim",
    cmd = "BlameToggle",
    opts = {
      max_summary_width = 25,
      mappings = {
        commit_info = "i",
        stack_push = "<TAB>",
        stack_pop = "<BS>",
        show_commit = "<CR>",
        close = { "q" },
      },
      date_format = "%d.%m.%y",
      format_fn = function(line_porcelain, config, idx)
        local hash = string.sub(line_porcelain.hash, 0, 7)
        local line_with_hl = {}
        local is_commited = hash ~= "0000000"
        if is_commited then
          local summary
          if #line_porcelain.summary > config.max_summary_width then
            summary = string.sub(line_porcelain.summary, 0, config.max_summary_width - 3) .. "..."
          else
            summary = line_porcelain.summary
          end

          line_with_hl = {
            idx = idx,
            values = {
              {
                textValue = hash,
                hl = "Comment",
              },
              {
                textValue = os.date(config.date_format, line_porcelain.committer_time),
                hl = hash,
              },
              {
                textValue = line_porcelain.author:sub(0, 6),
                hl = hash,
              },
              {
                textValue = summary,
                hl = hash,
              },
            },
            format = "%s  %s  %s %s",
          }
        else
          line_with_hl = {
            idx = idx,
            values = {
              {
                textValue = "Not committed",
                hl = "Comment",
              },
            },
            format = "%s",
          }
        end
        return line_with_hl
      end,
    },
  },
}
