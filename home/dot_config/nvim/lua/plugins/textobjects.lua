return {
  { "wellle/targets.vim" },
  {
    "kana/vim-textobj-user",
    config = function()
      local textobj = vim.fn["textobj#user#plugin"]
      textobj("datetime", {
        date = {
          pattern = "\\<\\d\\d\\d\\d-\\d\\d-\\d\\d\\>",
          select = { "ad", "id" },
        },
        time = {
          pattern = "\\<\\d\\d:\\d\\d:\\d\\d\\>",
          select = { "at", "it" },
        },
      })
    end,
  },
  { "kana/vim-textobj-indent", dependencies = { "kana/vim-textobj-user" } },
  { "kana/vim-textobj-function", dependencies = { "kana/vim-textobj-user" } },
  { "kana/vim-textobj-entire", dependencies = { "kana/vim-textobj-user" } },
}
