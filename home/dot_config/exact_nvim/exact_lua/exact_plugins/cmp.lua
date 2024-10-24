local win_highlight = "Normal:Normal,FloatBorder:Normal,CursorLine:Visual,Search:None"
return {
  {
    "hrsh7th/nvim-cmp",
    dependencies = {
      { "hrsh7th/cmp-nvim-lsp-signature-help" },
      {
        "rcarriga/cmp-dap",
        dependencies = {
          { "mfussenegger/nvim-dap" },
        },
      },
      { "lukas-reineke/cmp-rg" },
      { "lukas-reineke/cmp-under-comparator" },
      { "petertriho/cmp-git", config = true },
      { "SergioRibera/cmp-dotenv" },
      { "hrsh7th/cmp-emoji" },
      { "amarakon/nvim-cmp-fonts" },
    },
    opts = function(_, opts)
      local cmp = require("cmp")
      table.insert(opts.sources, { name = "nvim_lsp_signature_help" })
      table.insert(opts.sources, { name = "rg", keyword_length = 3 })
      table.insert(opts.sorting.comparators, 4, require("cmp-under-comparator").under)
      table.insert(opts.sources, { name = "dotenv" })
      table.insert(opts.sources, { name = "emoji" })
      table.insert(opts.sources, { name = "fonts", option = { space_filter = "-" } })

      opts.window = {
        completion = {
          border = "rounded",
          winhighlight = win_highlight,
        },
        documentation = {
          border = "rounded",
          winhighlight = win_highlight,
        },
      }

      cmp.setup.filetype("gitcommit", {
        sources = cmp.config.sources({
          { name = "git" }, -- You can specify the `git` source if [you were installed it](https://github.com/petertriho/cmp-git).
        }, {
          { name = "buffer" },
        }),
      })

      cmp.setup.filetype({ "dap-repl" }, {
        sources = {
          { name = "dap" },
        },
      })

      cmp.setup.filetype({ "sql" }, {
        sources = {
          { name = "vim-dadbod-completion" },
          { name = "buffer" },
        },
      })
    end,
  },
}
