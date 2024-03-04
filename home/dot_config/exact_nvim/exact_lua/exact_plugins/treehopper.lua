return {
  "mfussenegger/nvim-treehopper",
  keys = {
    {
      "t",
      function()
        require("tsht").nodes()
      end,
      mode = { "o", "x", "v" },
    },
  },
}
