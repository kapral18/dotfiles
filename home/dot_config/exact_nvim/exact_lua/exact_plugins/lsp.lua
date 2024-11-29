-- enabled if noice.nvim is off
vim.lsp.handlers["textDocument/hover"] = function(_, result, ctx, config)
  config = config or {}
  config.focus_id = ctx.method
  if not (result and result.contents) then
    return
  end
  local markdown_lines = vim.lsp.util.convert_input_to_markdown_lines(result.contents)
  markdown_lines = vim.lsp.util.trim_empty_lines(markdown_lines)
  if vim.tbl_isempty(markdown_lines) then
    return
  end
  return vim.lsp.util.open_floating_preview(markdown_lines, "markdown", config)
end

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
      backend = { "nui" },
      diff = {
        algorithm = "patience",
        ignore_whitespace = true,
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
          keys[#keys + 1] = { "gD", false }
          keys[#keys + 1] = { "gI", false }
        end,
      },
    },
    opts = {
      border = {
        enable = true,
      },
      detached = true,
      height = 30,
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
      { "gd", "<CMD>Glance definitions<CR>", desc = "Goto Definitions" },
      { "gr", "<CMD>Glance references<CR>", desc = "References" },
      { "gy", "<CMD>Glance type_definitions<CR>", desc = "Goto t[y]pe definitions" },
      { "gI", "<CMD>Glance implementations<CR>", desc = "Goto Implementations" },
    },
  },
  {
    "0oAstro/dim.lua",
    event = "LspAttach",
    opts = {
      disable_lsp_decorations = true,
    },
  },
  {
    "linrongbin16/lsp-progress.nvim",
    opts = {},
    dependencies = {
      {
        "nvim-lualine/lualine.nvim",
        config = function(_, opts)
          local new_opts = {
            sections = {
              lualine_y = {
                function()
                  -- invoke `progress` here.
                  return require("lsp-progress").progress()
                end,
              },
            },
          }
          opts = vim.tbl_deep_extend("force", opts, new_opts)
          require("lualine").setup(opts)

          -- listen lsp-progress event and refresh lualine
          vim.api.nvim_create_augroup("lualine_augroup", { clear = true })
          vim.api.nvim_create_autocmd("User", {
            group = "lualine_augroup",
            pattern = "LspProgressStatusUpdated",
            callback = require("lualine").refresh,
          })
        end,
      },
    },
  },
}
