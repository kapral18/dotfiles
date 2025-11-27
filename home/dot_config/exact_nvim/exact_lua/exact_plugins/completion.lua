local tabouts = {
  { open = "'", close = "'" },
  { open = '"', close = '"' },
  { open = "`", close = "`" },
  { open = "(", close = ")" },
  { open = "[", close = "]" },
  { open = "{", close = "}" },
  { open = "<", close = ">" },
}

return {
  {
    "saghen/blink.compat",
    lazy = true,
    opts = {},
    version = "*",
  },
  {
    "saghen/blink.cmp",
    version = "*",
    dependencies = {
      "rafamadriz/friendly-snippets",
      -- Compat sources
      "lukas-reineke/cmp-rg",
      "hrsh7th/cmp-emoji",
      "SergioRibera/cmp-dotenv",
      "amarakon/nvim-cmp-fonts",
      { "github/copilot.vim", optional = true },
    },
    init = function()
      vim.g.copilot_no_tab_map = true
      vim.g.copilot_assume_mapped = true
      vim.g.copilot_tab_fallback = ""
    end,
    event = { "InsertEnter", "CmdlineEnter" },
    opts = function()
      return {
        keymap = {
          preset = "none",
          ["<C-space>"] = { "show", "show_documentation", "hide_documentation" },
          ["<C-e>"] = { "hide", "fallback" },
          ["<CR>"] = { "accept", "fallback" },
          ["<Up>"] = { "select_prev", "fallback" },
          ["<Down>"] = { "select_next", "fallback" },
          ["<C-b>"] = { "scroll_documentation_up", "fallback" },
          ["<C-f>"] = { "scroll_documentation_down", "fallback" },
          ["<C-n>"] = { "select_next", "snippet_forward", "show", "fallback" },
          ["<C-p>"] = { "select_prev", "snippet_backward", "fallback" },

          ["<Tab>"] = {
            function(cmp)
              -- 1. Copilot
              local copilot_keys = vim.fn["copilot#Accept"]()
              if copilot_keys ~= "" and type(copilot_keys) == "string" then
                vim.api.nvim_feedkeys(copilot_keys, "n", true)
                return true
              end

              -- 2. Tabout
              local cursor = vim.api.nvim_win_get_cursor(0)
              local cur_col = cursor[2]
              local current_line = vim.api.nvim_get_current_line()
              local char_after_cursor = current_line:sub(cur_col + 1, cur_col + 1)

              local should_tabout = false
              for _, tabout in ipairs(tabouts) do
                if tabout.close == char_after_cursor or tabout.open == char_after_cursor then
                  should_tabout = true
                  break
                end
              end

              if should_tabout then
                vim.api.nvim_feedkeys(vim.api.nvim_replace_termcodes("<Right>", true, true, true), "n", true)
                return true
              end
            end,
            "snippet_forward",
            "fallback",
          },
          ["<S-Tab>"] = {
            function(cmp)
              -- Tabout backwards
              local cursor = vim.api.nvim_win_get_cursor(0)
              local cur_col = cursor[2]
              local current_line = vim.api.nvim_get_current_line()
              local char_before_cursor = current_line:sub(cur_col, cur_col)

              local should_tabout = false
              for _, tabout in ipairs(tabouts) do
                if tabout.close == char_before_cursor or tabout.open == char_before_cursor then
                  should_tabout = true
                  break
                end
              end

              if should_tabout then
                vim.api.nvim_feedkeys(vim.api.nvim_replace_termcodes("<Left>", true, true, true), "n", true)
                return true
              end
            end,
            "snippet_backward",
            "fallback",
          },
        },
        appearance = {
          use_nvim_cmp_as_default = true,
          nerd_font_variant = "mono",
        },
        sources = {
          default = { "lsp", "path", "snippets", "buffer", "rg", "emoji", "dotenv", "fonts" },
          providers = {
            rg = {
              name = "rg",
              module = "blink.compat.source",
              score_offset = -3,
            },
            emoji = {
              name = "emoji",
              module = "blink.compat.source",
              score_offset = -3,
            },
            dotenv = {
              name = "dotenv",
              module = "blink.compat.source",
              score_offset = -3,
            },
            fonts = {
              name = "fonts",
              module = "blink.compat.source",
              score_offset = -3,
              opts = { space_filter = "-" },
            },
          },
        },
        signature = { enabled = true },
      }
    end,
  },
}
