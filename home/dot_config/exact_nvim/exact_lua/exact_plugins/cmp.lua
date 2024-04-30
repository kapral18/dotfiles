return {
  {
    "hrsh7th/nvim-cmp",
    dependencies = {
      { "lukas-reineke/cmp-rg" },
      { "lukas-reineke/cmp-under-comparator" },
      { "chrisgrieser/cmp-nerdfont" },
      { "petertriho/cmp-git", config = true },
      { "SergioRibera/cmp-dotenv" },
      { "hrsh7th/cmp-emoji" },
      { "amarakon/nvim-cmp-fonts" },
    },
    opts = function(_, opts)
      local cmp = require("cmp")
      table.insert(opts.sources, { name = "rg", keyword_length = 3 })
      table.insert(opts.sorting.comparators, 4, require("cmp-under-comparator").under)
      table.insert(opts.sources, { name = "dotenv" })
      table.insert(opts.sources, { name = "emoji" })
      table.insert(opts.sources, { name = "fonts", option = { space_filter = "-" } })
      table.insert(opts.sources, { name = "nerdfont" })

      cmp.setup.filetype("gitcommit", {
        sources = cmp.config.sources({
          { name = "git" }, -- You can specify the `git` source if [you were installed it](https://github.com/petertriho/cmp-git).
        }, {
          { name = "buffer" },
        }),
      })
    end,
  },
}
