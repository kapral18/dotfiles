return {
  "arsham/archer.nvim",
  name = "archer.nvim",
  dependencies = { "arsham/arshlib.nvim" },
  event = { "BufReadPost", "BufNewFile" },
  opts = {
    mappings = {
      space = {
        above = "[<space>",
        below = "]<space>",
      },
      ending = false,
      brackets = false,
      augment_vim = false,
    },
  },
}
