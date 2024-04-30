return {
  {
    "aznhe21/actions-preview.nvim",
    init = function()
      local keys = require("lazyvim.plugins.lsp.keymaps").get()

      keys[#keys + 1] = { "<leader>ca", false }
    end,
    event = "LspAttach",
    opts = {
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
    "zeioth/garbage-day.nvim",
    event = "LspAttach",
    opts = {
      notifications = true,
      grace_period = 60 * 10,
    },
  },
  {
    "dnlhc/glance.nvim",
    init = function()
      local keys = require("lazyvim.plugins.lsp.keymaps").get()

      keys[#keys + 1] = { "gd", false }
      keys[#keys + 1] = { "gr", false }
      keys[#keys + 1] = { "gy", false }
      keys[#keys + 1] = { "gI", false }
    end,
    cmd = { "Glance" },
    opts = {
      border = {
        enable = true,
      },
      use_trouble_qf = true,
      hooks = {
        before_open = function(results, open, jump, method)
          local uri = vim.uri_from_bufnr(0)
          if #results == 1 then
            local target_uri = results[1].uri or results[1].targetUri

            if target_uri == uri then
              jump(results[1])
            else
              open(results)
            end
          else
            open(results)
          end
        end,
      },
    },
    keys = {
      { "gd", "<CMD>Glance definitions<CR>", desc = "Goto Definition" },
      { "gr", "<CMD>Glance references<CR>", desc = "References" },
      { "gy", "<CMD>Glance type_definitions<CR>", desc = "Goto t[y]pe definitions" },
      { "gI", "<CMD>Glance implementations<CR>", desc = "Goto implementations" },
    },
  },
  {
    "smjonas/inc-rename.nvim",
    cmd = "IncRename",
    opts = {},
  },
  {
    "VidocqH/lsp-lens.nvim",
    event = "LspAttach",
    opts = {
      sections = {
        definition = false,
        references = function(count)
          return "󰌹 Ref: " .. count
        end,
        implements = function(count)
          return "󰡱 Imp: " .. count
        end,
        git_authors = false,
      },
    },
    keys = {
      { "<leader>ue", "<cmd>LspLensToggle<cr>", desc = "Toggle Lsp Lens" },
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
    "zbirenbaum/neodim",
    event = "LspAttach",
    opts = {
      alpha = 0.60,
    },
    -- enable after 0.10
    enabled = false,
  },
  {
    "artemave/workspace-diagnostics.nvim",
    event = "LspAttach",
    opts = {},
  },
}
