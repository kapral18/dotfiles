vim.filetype.add({
  pattern = {
    [".*%.mdx"] = "markdown",
    ["README"] = "markdown",
  },
})

return {
  {
    "MeanderingProgrammer/render-markdown.nvim",
    enabled = false,
  },
}
