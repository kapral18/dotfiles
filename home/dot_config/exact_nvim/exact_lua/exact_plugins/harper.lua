return {
  {
    "neovim/nvim-lspconfig",
    opts = {
      servers = {
        harper_ls = {
          filetypes = { "gitcommit", "mail", "text" },
          linters = {
            SpellCheck = true,
            SpelledNumbers = false,
            AnA = true,
            SentenceCapitalization = true,
            UnclosedQuotes = true,
            WrongQuotes = false,
            LongSentences = true,
            RepeatedWords = true,
            Spaces = true,
            Matcher = true,
            CorrectNumberSuffix = true,
          },
          codeActions = {
            ForceStable = false,
          },
          diagnosticSeverity = "hint",
          dialect = "American", -- or British, Canadian, Australian
        },
      },
    },
  },
}
