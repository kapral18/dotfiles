local util = require("util")

local tabouts = {
  { open = "'", close = "'" },
  { open = '"', close = '"' },
  { open = "`", close = "`" },
  { open = "(", close = ")" },
  { open = "[", close = "]" },
  { open = "{", close = "}" },
  { open = "<", close = ">" },
}

local unpack = unpack or table.unpack

local has_words_before = function()
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

local win_highlight = "Normal:Normal,FloatBorder:Normal,CursorLine:Visual,Search:None"

return {
  {
    "hrsh7th/nvim-cmp",
    event = { "InsertEnter", "CmdlineEnter" },
    dependencies = {
      "hrsh7th/cmp-nvim-lsp",
      "hrsh7th/cmp-buffer",
      "hrsh7th/cmp-path",
      "hrsh7th/cmp-cmdline",
      "hrsh7th/cmp-nvim-lsp-signature-help",
      "lukas-reineke/cmp-rg",
      "lukas-reineke/cmp-under-comparator",
      "SergioRibera/cmp-dotenv",
      "hrsh7th/cmp-emoji",
      "amarakon/nvim-cmp-fonts",
      { "github/copilot.vim", optional = true },
    },
    -- overriding lazyvim native snippets tab behavior
    keys = function()
      return {}
    end,
    init = function()
      vim.g.copilot_no_tab_map = true
      vim.g.copilot_assume_mapped = true
      vim.g.copilot_tab_fallback = ""
    end,
    opts = function()
      local cmp = require("cmp")

      local mapping = {
        ["<Tab>"] = cmp.mapping(function(fallback)
          local cur_row, cur_col = unpack(vim.api.nvim_win_get_cursor(0))
          local current_line = vim.api.nvim_get_current_line()
          local char_after_cursor = current_line:sub(cur_col + 1, cur_col + 1)

          local tabout_symbols = {}
          for _, tabout in ipairs(tabouts) do
            table.insert(tabout_symbols, tabout.open)
            table.insert(tabout_symbols, tabout.close)
          end

          if vim.b.copilot_enabled == 1 or vim.b.copilot_enabled == true then
            local suggestion = vim.fn["copilot#GetDisplayedSuggestion"]() or {}
            if suggestion.text and suggestion.text ~= "" then
              local copilot_keys = vim.fn["copilot#Accept"]()
              if copilot_keys ~= "" then
                vim.api.nvim_feedkeys(copilot_keys, "i", true)
                return
              end
            end
          end

          if vim.b.codeium_enabled then
            local ok_status, status = pcall(vim.fn["codeium#GetStatusString"])
            status = ok_status and status or ""
            if type(status) == "string" and status:match("^%d+/%d+$") then
              -- Temporarily disable diagnostics
              vim.diagnostic.enable(false)
              local ok_acc, ret = pcall(vim.fn["codeium#Accept"])
              if ok_acc and type(ret) == "string" and ret ~= "" then
                vim.api.nvim_feedkeys(ret, "i", true)
                -- Re-enable diagnostics after a short delay
                vim.defer_fn(function()
                  vim.diagnostic.enable()
                end, 100)
                return
              end
              vim.diagnostic.enable(true) -- Re-enable if insertion failed
            end
          end

          if vim.tbl_contains(tabout_symbols, char_after_cursor) then
            vim.api.nvim_win_set_cursor(0, { cur_row, cur_col + 1 })
          else
            fallback()
          end
        end, { "i", "s" }),

        ["<S-Tab>"] = cmp.mapping(function(fallback)
          local cur_row, cur_col = unpack(vim.api.nvim_win_get_cursor(0))
          local current_line = vim.api.nvim_get_current_line()
          local char_before_cursor = current_line:sub(cur_col, cur_col)
          local tabout_symbols = {}
          for _, tabout in ipairs(tabouts) do
            table.insert(tabout_symbols, tabout.open)
            table.insert(tabout_symbols, tabout.close)
          end

          if vim.tbl_contains(tabout_symbols, char_before_cursor) then
            vim.api.nvim_win_set_cursor(0, { cur_row, cur_col - 1 })
          else
            vim.api.nvim_feedkeys(vim.api.nvim_replace_termcodes("<C-d>", true, true, true), "n", {})
          end
        end, { "i", "s" }),

        ["<C-n>"] = cmp.mapping(function(fallback)
          if cmp.visible() then
            cmp.select_next_item()
            -- You could replace the expand_or_jumpable() calls with expand_or_locally_jumpable()
            -- this way you will only jump inside the snippet region
          elseif vim.snippet.active({ direction = 1 }) then
            vim.schedule(function()
              vim.snippet.jump(1)
            end)
          elseif has_words_before() then
            cmp.complete()
          else
            fallback()
          end
        end, { "i", "s" }),

        ["<C-p>"] = cmp.mapping(function(fallback)
          if cmp.visible() then
            cmp.select_prev_item()
          elseif vim.snippet.active({ direction = -1 }) then
            vim.schedule(function()
              vim.snippet.jump(-1)
            end)
          else
            vim.api.nvim_feedkeys(vim.api.nvim_replace_termcodes("<C-d>", true, true, true), "n", {})
          end
        end, { "i", "s" }),

        ["<CR>"] = cmp.mapping.confirm({ select = false }),
      }

      return {
        completion = { completeopt = "menu,menuone,noinsert,noselect" },
        preselect = cmp.PreselectMode.None,
        experimental = { ghost_text = false },
        mapping = cmp.mapping.preset.insert(mapping),
        window = {
          completion = {
            border = "rounded",
            winhighlight = win_highlight,
          },
          documentation = {
            border = "rounded",
            winhighlight = win_highlight,
          },
        },
        formatting = {
          format = function(entry, item)
            local icons = (util.config and util.config.icons and util.config.icons.kinds) or {}
            if icons[item.kind] then
              item.kind = icons[item.kind] .. item.kind
            end
            return item
          end,
        },
        sources = cmp.config.sources({
          { name = "nvim_lsp" },
          { name = "nvim_lsp_signature_help" },
          { name = "path" },
          { name = "dotenv" },
          { name = "emoji" },
          { name = "fonts",                  option = { space_filter = "-" } },
        }, {
          { name = "buffer" },
          { name = "rg",    keyword_length = 3 },
        }),
        sorting = {
          priority_weight = 2,
          comparators = {
            require("cmp-under-comparator").under,
            cmp.config.compare.offset,
            cmp.config.compare.exact,
            cmp.config.compare.score,
            cmp.config.compare.recently_used,
            cmp.config.compare.locality,
            cmp.config.compare.kind,
            cmp.config.compare.sort_text,
            cmp.config.compare.length,
            cmp.config.compare.order,
          },
        },
      }
    end,
    config = function(_, opts)
      local cmp = require("cmp")
      cmp.setup(opts)
      cmp.setup.cmdline("/", {
        mapping = cmp.mapping.preset.cmdline(),
        sources = { { name = "buffer" } },
      })
      cmp.setup.cmdline(":", {
        mapping = cmp.mapping.preset.cmdline(),
        sources = cmp.config.sources({ { name = "path" } }, { { name = "cmdline" } }),
      })
      cmp.setup.filetype("dap-repl", {
        sources = {
          { name = "dap" },
        },
      })
    end,
  },
}
