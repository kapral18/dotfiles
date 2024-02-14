return {
  "jbyuki/one-small-step-for-vimkind",
  keys = {
    { "<F5>", [[:lua require"osv".launch({port = 8086})<CR>]], desc = "Launch OSV", noremap = true },
  },
}
