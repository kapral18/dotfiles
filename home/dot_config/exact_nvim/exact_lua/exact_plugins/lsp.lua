-- -- enable if noice.nvim is off
-- vim.lsp.handlers["textDocument/hover"] = function(_, result, ctx, config)
--   config = config or {}
--   config.focus_id = ctx.method
--   if not (result and result.contents) then
--     return
--   end
--   local markdown_lines = vim.lsp.util.convert_input_to_markdown_lines(result.contents)
--   markdown_lines = vim.lsp.util.trim_empty_lines(markdown_lines)
--   if vim.tbl_isempty(markdown_lines) then
--     return
--   end
--   return vim.lsp.util.open_floating_preview(markdown_lines, "markdown", config)
-- end

return {
  {
    "neovim/nvim-lspconfig",
    opts = {
      inlay_hints = { enabled = false },
    },
  },
  {
    "aznhe21/actions-preview.nvim",
    event = "LspAttach",
    dependencies = {
      {
        "neovim/nvim-lspconfig",
        opts = function()
          local keys = require("lazyvim.plugins.lsp.keymaps").get()

          keys[#keys + 1] = { "<leader>ca", false }
        end,
      },
    },
    opts = {
      diff = {
        algorithm = "patience",
        ignore_whitespace = true,
      },
      telescope = {
        sorting_strategy = "ascending",
        layout_strategy = "vertical",
        layout_config = {
          width = 0.6,
          height = 0.7,
          prompt_position = "top",
          preview_cutoff = 20,
          preview_height = function(_, _, max_lines)
            return max_lines - 15
          end,
        },
      },
    },
    keys = {
      {
        "<leader>ca",
        function()
          require("actions-preview").code_actions()
        end,
        mode = { "n", "v" },
        desc = "Code Action Preview",
      },
    },
  },
  {
    "dnlhc/glance.nvim",
    dependencies = {
      {
        "neovim/nvim-lspconfig",
        opts = function()
          local keys = require("lazyvim.plugins.lsp.keymaps").get()

          keys[#keys + 1] = { "gd", false }
          keys[#keys + 1] = { "gr", false }
          keys[#keys + 1] = { "gy", false }
          keys[#keys + 1] = { "gI", false }
        end,
      },
    },
    opts = {
      border = {
        enable = true,
      },
      use_trouble_qf = false,
      hooks = {
        before_open = function(results, open, jump, method)
          local filter = function(arr, fn)
            if type(arr) ~= "table" then
              return arr
            end

            local filtered = {}
            for k, v in pairs(arr) do
              if fn(v, k, arr) then
                table.insert(filtered, v)
              end
            end

            return filtered
          end

          local filterReactDTS = function(value)
            if value.uri then
              return string.match(value.uri, "%.d%.ts") == nil
            elseif value.targetUri then
              return string.match(value.targetUri, "%.d%.ts") == nil
            end
          end

          if #results == 1 then
            jump(results[1])
          elseif method == "definitions" then
            local filtered_results = filter(results, filterReactDTS)
            if #filtered_results == 1 then
              jump(filtered_results[1])
            -- covering edge case when all results are d.ts so we want to show them
            -- otherwise errors out with empty panel
            elseif #filtered_results == 0 then
              open(results)
            else
              open(filtered_results)
            end
          else
            open(results)
          end
        end,
      },
    },
    cmd = { "Glance" },
    keys = {
      { "gd", "<CMD>Glance definitions<CR>", desc = "Goto Definition" },
      { "gr", "<CMD>Glance references<CR>", desc = "References" },
      { "gy", "<CMD>Glance type_definitions<CR>", desc = "Goto t[y]pe definitions" },
      { "gI", "<CMD>Glance implementations<CR>", desc = "Goto implementations" },
    },
  },
  {
    "kosayoda/nvim-lightbulb",
    event = "LspAttach",
    opts = {
      autocmd = { enabled = true },
      sign = { enabled = true, text = "" },
      action_kinds = { "quickfix", "refactor" },
      ignore = {
        actions_without_kind = true,
      },
    },
  },
  {
    "0oAstro/dim.lua",
    event = "LspAttach",
    opts = {
      disable_lsp_decorations = true,
    },
  },
  -- disagnostics off in input mode
  {
    "yorickpeterse/nvim-dd",
    event = "LspAttach",
    opts = {
      timeout = 1000,
    },
  },
  {
    "lewis6991/hover.nvim",
    dependencies = {
      {
        "neovim/nvim-lspconfig",
        opts = function()
          local keys = require("lazyvim.plugins.lsp.keymaps").get()

          keys[#keys + 1] = { "K", false }
          keys[#keys + 1] = { "gK", false }
          keys[#keys + 1] = { "<c-k>", false }
        end,
      },
    },
    opts = {
      init = function()
        require("hover.providers.lsp")
        require("hover.providers.gh")
        require("hover.providers.gh_user")
        require("hover.providers.jira")
        require("hover.providers.dap")
        require("hover.providers.fold_preview")
        require("hover.providers.diagnostic")
        require("hover.providers.man")
        require("hover.providers.dictionary")
      end,
      preview_opts = {
        border = "single",
      },
      preview_window = false,
      title = true,
      mouse_providers = {
        "LSP",
      },
      mouse_delay = 1000,
    },
    keys = {
      -- Setup keymaps
      -- stylua: ignore start
      { "K", function() require("hover").hover() end, desc = "hover.nvim",  },
      { "<c-k>", function() require("hover").hover() end, mode = "i", desc = "hover.nvim",  },
      { "gK", function() require("hover").hover_select() end, desc = "hover.nvim (select)",  },
      { "[k", function() require("hover").hover_switch("previous") end, desc = "hover.nvim (previous source)",  },
      { "]k", function() require("hover").hover_switch("next") end, desc = "hover.nvim (next source)",  },
      -- Mouse support
      { "<MouseMove>", function() require("hover").hover_mouse() end, desc = "hover.nvim (mouse)",  },
      -- stylua: ignore end
    },
  },
}
