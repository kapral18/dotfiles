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
  -- Use <tab> for completion and snippets (supertab)
  -- first: disable default <tab> and <s-tab> behavior in LuaSnip
  {
    "L3MON4D3/LuaSnip",
    keys = function()
      return {}
    end,
  },
  -- then: setup supertab in cmp
  {
    "hrsh7th/nvim-cmp",
    dependencies = {
      {
        "abecodes/tabout.nvim",
        config = function()
          require("tabout").setup({
            tabkey = "", -- key to trigger tabout, set to an empty string to disable
            backwards_tabkey = "", -- key to trigger backwards tabout, set to an empty string to disable
            act_as_tab = false, -- shift content if tab out is not possible
            act_as_shift_tab = false, -- reverse shift content if tab out is not possible (if your keyboard/terminal supports <S-Tab>)
            default_tab = "", -- shift default action (only at the beginning of a line, otherwise <TAB> is used)
            default_shift_tab = "", -- reverse shift default action,
            enable_backwards = true, -- well ...
            completion = false, -- if the tabkey is used in a completion pum
            tabouts = tabouts,
            ignore_beginning = false, --[[ if the cursor is at the beginning of a filled element it will rather tab out than shift the content ]]
            exclude = {}, -- tabout will ignore these filetypes
          })
        end,
        dependencies = { -- These are optional
          "nvim-treesitter/nvim-treesitter",
        },
      },
      {
        "L3MON4D3/LuaSnip",
        keys = function()
          -- Disable default tab keybinding in LuaSnip
          return {}
        end,
      },
    },
    ---@param opts cmp.ConfigSchema
    opts = function(_, opts)
      local has_words_before = function()
        unpack = unpack or table.unpack
        local _, cur_col = unpack(vim.api.nvim_win_get_cursor(0))
        if cur_col == 0 then
          return false
        end

        local current_line = vim.api.nvim_get_current_line()
        -- cur_row is 1 based but cur_col is 0-based so when used with 1-based api
        -- like :sub() it actually points at -1 char from actual position of cur_col
        -- so if previous char does not match empty string
        -- we consider that there are words before
        local char_before = current_line:sub(cur_col, cur_col)
        return char_before:match("%s") == nil
      end

      local luasnip = require("luasnip")
      local cmp = require("cmp")

      opts.mapping = vim.tbl_extend("force", opts.mapping, {
        ["<Tab>"] = cmp.mapping(function(fallback)
          unpack = unpack or table.unpack
          local _, cur_col = unpack(vim.api.nvim_win_get_cursor(0))
          local current_line = vim.api.nvim_get_current_line()
          local char_after_cursor = current_line:sub(cur_col + 1, cur_col + 1)
          local tabout_symbols = {}
          for _, tabout in ipairs(tabouts) do
            table.insert(tabout_symbols, tabout.open)
            table.insert(tabout_symbols, tabout.close)
          end

          if vim.tbl_contains(tabout_symbols, char_after_cursor) and require("tabout").is_enabled() then
            require("tabout").tabout()
          elseif cmp.visible() then
            cmp.select_next_item()
            -- You could replace the expand_or_jumpable() calls with expand_or_locally_jumpable()
            -- this way you will only jump inside the snippet region
          elseif luasnip.expand_or_jumpable() then
            luasnip.expand_or_jump()
          elseif has_words_before() then
            cmp.complete()
          else
            fallback()
          end
        end, { "i", "s" }),
        ["<S-Tab>"] = cmp.mapping(function(fallback)
          unpack = unpack or table.unpack
          local _, cur_col = unpack(vim.api.nvim_win_get_cursor(0))
          local current_line = vim.api.nvim_get_current_line()
          local char_before_cursor = current_line:sub(cur_col, cur_col)
          local tabout_symbols = {}
          for _, tabout in ipairs(tabouts) do
            table.insert(tabout_symbols, tabout.open)
            table.insert(tabout_symbols, tabout.close)
          end

          if vim.tbl_contains(tabout_symbols, char_before_cursor) and require("tabout").is_enabled() then
            require("tabout").taboutBack()
          elseif cmp.visible() then
            cmp.select_prev_item()
          elseif luasnip.jumpable(-1) then
            luasnip.jump(-1)
          else
            vim.api.nvim_feedkeys(vim.api.nvim_replace_termcodes("<C-d>", true, true, true), "n", {})
          end
        end, { "i", "s" }),
        -- Accept currently selected item. Set `select` to `false` to only confirm explicitly selected items
        ["<CR>"] = cmp.mapping.confirm({ select = false }),
      })

      -- works in conjunction with <CR> mapping.confirm({select = false})
      opts.completion.completeopt = "menu,menuone,noinsert,noselect"
    end,
  },
}
