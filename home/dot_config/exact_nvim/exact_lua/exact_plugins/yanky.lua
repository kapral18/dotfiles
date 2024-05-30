return {
  {
    "gbprod/yanky.nvim",
    opts = function(_, opts)
      local utils = require("yanky.utils")
      local mapping = require("yanky.telescope.mapping")

      opts.highlight = { timer = 250 }
      opts.ring = { storage = "shada" }
      opts.picker = {
        telescope = {
          use_default_mappings = false,
          mappings = {
            default = mapping.put("p"),
            i = {
              ["<c-x>"] = mapping.delete(),
            },
          },
        },
      }
    end,
    -- stylua: ignore
    keys = {
      {"<leader>sy", function() require("telescope").extensions.yank_history.yank_history({}) end, mode = {"n", "v"}, desc = "Yank History"},
    },
  },
  {
    "hrsh7th/nvim-cmp",
    dependencies = {
      "chrisgrieser/cmp_yanky",
    },
    opts = function(_, opts)
      table.insert(opts.sources, { name = "cmp_yanky" })
    end,
  },
}
