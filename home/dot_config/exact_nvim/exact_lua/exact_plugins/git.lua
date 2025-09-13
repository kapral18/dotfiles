local common_utils = require("utils.common")

return {
  {
    "lewis6991/gitsigns.nvim",
    version = "*",
    event = "LazyFile",
    opts = {
      -- visuals
      signs = {
        add = { text = "▎" },
        change = { text = "▎" },
        delete = { text = "" },
        topdelete = { text = "" },
        changedelete = { text = "▎" },
        untracked = { text = "▎" },
      },
      signs_staged = {
        add = { text = "▎" },
        change = { text = "▎" },
        delete = { text = "" },
        topdelete = { text = "" },
        changedelete = { text = "▎" },
      },
      signs_staged_enable = true,

      -- highlights and word diff
      numhl = true,
      linehl = false,
      word_diff = false,

      -- blame
      current_line_blame = true,
      current_line_blame_opts = {
        virt_text = true,
        virt_text_pos = "eol",
        delay = 500,
      },
      current_line_blame_formatter = "<author>, <author_time> . <summary>",

      -- core behavior
      attach_to_untracked = false,
      update_debounce = 500,

      -- buffer-local mappings
      on_attach = function(buffer)
        local gs = package.loaded.gitsigns
        local function map(mode, lhs, rhs, desc)
          vim.keymap.set(mode, lhs, rhs, { buffer = buffer, desc = desc })
        end

        -- navigation
        map("n", "]h", function()
          if vim.wo.diff then
            vim.cmd.normal({ "]c", bang = true })
          else
            gs.nav_hunk("next")
          end
        end, "Next Hunk")
        map("n", "[h", function()
          if vim.wo.diff then
            vim.cmd.normal({ "[c", bang = true })
          else
            gs.nav_hunk("prev")
          end
        end, "Prev Hunk")
        map("n", "]H", function()
          gs.nav_hunk("last")
        end, "Last Hunk")
        map("n", "[H", function()
          gs.nav_hunk("first")
        end, "First Hunk")

        -- actions
        map({ "n", "v" }, "<leader>ghs", ":Gitsigns stage_hunk<CR>", "Stage Hunk")
        map({ "n", "v" }, "<leader>ghr", ":Gitsigns reset_hunk<CR>", "Reset Hunk")
        map("n", "<leader>ghS", gs.stage_buffer, "Stage Buffer")
        map("n", "<leader>ghu", gs.undo_stage_hunk, "Undo Stage Hunk")
        map("n", "<leader>ghR", gs.reset_buffer, "Reset Buffer")

        -- previews
        map("n", "<leader>ghP", gs.preview_hunk_inline, "Preview Hunk Inline")
        map("n", "<leader>ghp", function()
          vim.cmd("Gitsigns preview_hunk")
        end, "Preview Hunk Popup")

        map("n", "<leader>ghd", gs.diffthis, "Diff This")
        map("n", "<leader>ghD", function()
          gs.diffthis("~")
        end, "Diff This ~")

        -- text object
        map({ "o", "x" }, "ih", ":<C-U>Gitsigns select_hunk<CR>", "Select Hunk")
      end,
    },

    -- global UI toggles
    keys = {
      { "<leader>ghtn", "<Cmd>Gitsigns toggle_numhl<CR>", desc = "Toggle Num Highlight" },
      { "<leader>ghtl", "<Cmd>Gitsigns toggle_linehl<CR>", desc = "Toggle Line Highlight" },
      { "<leader>ghtw", "<Cmd>Gitsigns toggle_word_diff<CR>", desc = "Toggle Word Diff" },
      { "<leader>ghtb", "<Cmd>Gitsigns toggle_current_line_blame<CR>", desc = "Toggle Blame Line" },
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
      return common_utils.get_git_root() ~= nil
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
      { "<leader>gar", ":AdvancedGitSearch search_log_content<CR>", desc = "AGS Repo History Search" },
      { "<leader>gaf", ":AdvancedGitSearch search_log_content_file<CR>", desc = "AGS File History Search" },
      { "<leader>gadf", ":AdvancedGitSearch diff_commit_file<CR>", desc = "AGS File vs commit" },
      { "<leader>gadl", ":AdvancedGitSearch diff_commit_line<CR>", mode = { "x" }, desc = "AGS Line vs commit" },
      { "<leader>gadb", ":AdvancedGitSearch diff_branch_file<CR>", desc = "AGS Branch vs commit" },
      { "<leader>gal", ":AdvancedGitSearch checkout_reflog<CR>", desc = "AGS Checkout reflog" },
    },
    opts = {
      -- diff_plugin = "diffview",
      show_builtin_git_pickers = true,
      entry_default_author_or_date = "date", -- one of "author" or "date"
    },
    config = function(_, opts)
      -- optional: setup telescope before loading the extension
      require("telescope").setup({
        -- move this to the place where you call the telescope setup function
        extensions = {
          advanced_git_search = opts,
        },
      })

      require("telescope").load_extension("advanced_git_search")

      -- require("advanced_git_search.fzf").setup(opts)

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
