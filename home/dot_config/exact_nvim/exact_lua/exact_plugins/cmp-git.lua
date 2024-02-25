local cmp = require("cmp")

return {
  "hrsh7th/nvim-cmp",
  dependencies = {
    "petertriho/cmp-git",
    opts = {},
  },
  opts = function()
    cmp.setup.filetype("gitcommit", {
      sources = cmp.config.sources({
        { name = "git" }, -- You can specify the `git` source if [you were installed it](https://github.com/petertriho/cmp-git).
      }, {
        { name = "buffer" },
      }),
    })
  end,
}
