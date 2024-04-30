return {
  {
    "nvim-treesitter/nvim-treesitter",
    dependencies = {
      "RRethy/nvim-treesitter-endwise",
      "chrisgrieser/nvim-puppeteer",
    },
    opts = {
      endwise = {
        enable = true,
      },
    },
  },
  {
    "echasnovski/mini.pairs",
    enabled = false,
  },
  {
    "windwp/nvim-autopairs",
    event = "InsertEnter",
    config = true,
    -- use opts = {} for passing setup options
    -- this is equalent to setup({}) function
  },
  {
    "nvim-treesitter/nvim-treesitter-context",
    enabled = false,
  },
  {
    "Wansmer/sibling-swap.nvim",
    dependencies = "nvim-treesitter/nvim-treesitter",
    opts = {
      use_default_keymaps = false,
      highlight_node_at_cursor = true,
    },
    keys = {
      {
        "<leader>.",
        function()
          -- swap with right and change operator in between
          require("sibling-swap").swap_with_right_with_opp()
        end,
        desc = "Move Node Right With Opp",
      },
      {
        "<leader>,",
        function()
          -- swap with right and change operator in between
          require("sibling-swap").swap_with_left_with_opp()
        end,
        desc = "Move Node Left With Opp",
      },
    },
  },
  {
    "nmac427/guess-indent.nvim",
    opts = {},
  },
  {
    "echasnovski/mini.align",
    opts = {},
  },
  {
    "ckolkey/ts-node-action",
    dependencies = { "nvim-treesitter" },
    opts = {},
    keys = {
      { "<leader>j", "<cmd>NodeAction<cr>", mode = "n", desc = "Node action" },
    },
  },
  {
    "johmsalas/text-case.nvim",
    lazy = false,
    keys = {
      {
        "<leader>ccau",
        ":lua require('textcase').current_word('to_upper_case')<CR>",
        desc = "current_word('to_upper_case')<CR>",
        mode = { "x", "n", "o" },
      },
      {
        "<leader>ccal",
        ":lua require('textcase').current_word('to_lower_case')<CR>",
        desc = "current_word('to_lower_case')<CR>",
        mode = { "x", "n", "o" },
      },
      {
        "<leader>ccas",
        ":lua require('textcase').current_word('to_snake_case')<CR>",
        desc = "current_word('to_snake_case')<CR>",
        mode = { "x", "n", "o" },
      },
      {
        "<leader>ccad",
        ":lua require('textcase').current_word('to_dash_case')<CR>",
        desc = "current_word('to_dash_case')<CR>",
        mode = { "x", "n", "o" },
      },
      {
        "<leader>ccan",
        ":lua require('textcase').current_word('to_constant_case')<CR>",
        desc = "current_word('to_constant_case')<CR>",
        mode = { "x", "n", "o" },
      },
      {
        "<leader>ccad",
        ":lua require('textcase').current_word('to_dot_case')<CR>",
        desc = "current_word('to_dot_case')<CR>",
        mode = { "x", "n", "o" },
      },
      {
        "<leader>ccaa",
        ":lua require('textcase').current_word('to_phrase_case')<CR>",
        desc = "current_word('to_phrase_case')<CR>",
        mode = { "x", "n", "o" },
      },
      {
        "<leader>ccac",
        ":lua require('textcase').current_word('to_camel_case')<CR>",
        desc = "current_word('to_camel_case')<CR>",
        mode = { "x", "n", "o" },
      },
      {
        "<leader>ccap",
        ":lua require('textcase').current_word('to_pascal_case')<CR>",
        desc = "current_word('to_pascal_case')<CR>",
        mode = { "x", "n", "o" },
      },
      {
        "<leader>ccat",
        ":lua require('textcase').current_word('to_title_case')<CR>",
        desc = "current_word('to_title_case')<CR>",
        mode = { "x", "n", "o" },
      },
      {
        "<leader>ccaf",
        ":lua require('textcase').current_word('to_path_case')<CR>",
        desc = "current_word('to_path_case')<CR>",
        mode = { "x", "n", "o" },
      },

      {
        "<leader>ccaU",
        ":lua require('textcase').lsp_rename('to_upper_case')<CR>",
        desc = "lsp_rename('to_upper_case')<CR>",
        mode = { "x", "n", "o" },
      },
      {
        "<leader>ccaL",
        ":lua require('textcase').lsp_rename('to_lower_case')<CR>",
        desc = "lsp_rename('to_lower_case')<CR>",
        mode = { "x", "n", "o" },
      },
      {
        "<leader>ccaS",
        ":lua require('textcase').lsp_rename('to_snake_case')<CR>",
        desc = "lsp_rename('to_snake_case')<CR>",
        mode = { "x", "n", "o" },
      },
      {
        "<leader>ccaD",
        ":lua require('textcase').lsp_rename('to_dash_case')<CR>",
        desc = "lsp_rename('to_dash_case')<CR>",
        mode = { "x", "n", "o" },
      },
      {
        "<leader>ccaN",
        ":lua require('textcase').lsp_rename('to_constant_case')<CR>",
        desc = "lsp_rename('to_constant_case')<CR>",
        mode = { "x", "n", "o" },
      },
      {
        "<leader>ccaD",
        ":lua require('textcase').lsp_rename('to_dot_case')<CR>",
        desc = "lsp_rename('to_dot_case')<CR>",
        mode = { "x", "n", "o" },
      },
      {
        "<leader>ccaA",
        ":lua require('textcase').lsp_rename('to_phrase_case')<CR>",
        desc = "lsp_rename('to_phrase_case')<CR>",
        mode = { "x", "n", "o" },
      },
      {
        "<leader>ccaC",
        ":lua require('textcase').lsp_rename('to_camel_case')<CR>",
        desc = "lsp_rename('to_camel_case')<CR>",
        mode = { "x", "n", "o" },
      },
      {
        "<leader>ccaP",
        ":lua require('textcase').lsp_rename('to_pascal_case')<CR>",
        desc = "lsp_rename('to_pascal_case')<CR>",
        mode = { "x", "n", "o" },
      },
      {
        "<leader>ccaT",
        ":lua require('textcase').lsp_rename('to_title_case')<CR>",
        desc = "lsp_rename('to_title_case')<CR>",
        mode = { "x", "n", "o" },
      },
      {
        "<leader>ccaF",
        ":lua require('textcase').lsp_rename('to_path_case')<CR>",
        desc = "lsp_rename('to_path_case')<CR>",
        mode = { "x", "n", "o" },
      },

      {
        "<leader>cceu",
        ":lua require('textcase').operator('to_upper_case')<CR>",
        desc = "operator('to_upper_case')<CR>",
        mode = { "x", "n", "o" },
      },
      {
        "<leader>ccel",
        ":lua require('textcase').operator('to_lower_case')<CR>",
        desc = "operator('to_lower_case')<CR>",
        mode = { "x", "n", "o" },
      },
      {
        "<leader>cces",
        ":lua require('textcase').operator('to_snake_case')<CR>",
        desc = "operator('to_snake_case')<CR>",
        mode = { "x", "n", "o" },
      },
      {
        "<leader>cced",
        ":lua require('textcase').operator('to_dash_case')<CR>",
        desc = "operator('to_dash_case')<CR>",
        mode = { "x", "n", "o" },
      },
      {
        "<leader>ccen",
        ":lua require('textcase').operator('to_constant_case')<CR>",
        desc = "operator('to_constant_case')<CR>",
        mode = { "x", "n", "o" },
      },
      {
        "<leader>cced",
        ":lua require('textcase').operator('to_dot_case')<CR>",
        desc = "operator('to_dot_case')<CR>",
        mode = { "x", "n", "o" },
      },
      {
        "<leader>ccea",
        ":lua require('textcase').operator('to_phrase_case')<CR>",
        desc = "operator('to_phrase_case')<CR>",
        mode = { "x", "n", "o" },
      },
      {
        "<leader>ccec",
        ":lua require('textcase').operator('to_camel_case')<CR>",
        desc = "operator('to_camel_case')<CR>",
        mode = { "x", "n", "o" },
      },
      {
        "<leader>ccep",
        ":lua require('textcase').operator('to_pascal_case')<CR>",
        desc = "operator('to_pascal_case')<CR>",
        mode = { "x", "n", "o" },
      },
      {
        "<leader>ccet",
        ":lua require('textcase').operator('to_title_case')<CR>",
        desc = "operator('to_title_case')<CR>",
        mode = { "x", "n", "o" },
      },
      {
        "<leader>ccef",
        ":lua require('textcase').operator('to_path_case')<CR>",
        desc = "operator('to_path_case')<CR>",
        mode = { "x", "n", "o" },
      },
    },
    opts = {
      default_keymappings_enabled = false,
    },
  },
  {
    "chrisgrieser/nvim-various-textobjs",
    opts = { useDefaultKeymaps = false },
    keys = {
      {
        "im",
        ft = { "markdown", "toml" },
        mode = { "o", "x" },
        function()
          require("various-textobjs").mdlink("inner")
        end,
        desc = "Markdown Link",
      },
      {
        "am",
        ft = { "markdown", "toml" },
        mode = { "o", "x" },
        function()
          require("various-textobjs").mdlink("outer")
        end,
        desc = "Markdown Link",
      },
      {
        "iC",
        ft = { "markdown" },
        mode = { "o", "x" },
        function()
          require("various-textobjs").mdFencedCodeBlock("inner")
        end,
        desc = "CodeBlock",
      },
      {
        "aC",
        ft = { "markdown" },
        mode = { "o", "x" },
        function()
          require("various-textobjs").mdFencedCodeBlock("outer")
        end,
        desc = "CodeBlock",
      },
      {
        "ie",
        ft = { "markdown" },
        mode = { "o", "x" },
        function()
          require("various-textobjs").mdEmphasis("inner")
        end,
        desc = "Emphasis",
      },
      {
        "ae",
        ft = { "markdown" },
        mode = { "o", "x" },
        function()
          require("various-textobjs").mdEmphasis("outer")
        end,
        desc = "Emphasis",
      },
      {
        "gd",
        mode = { "o", "x" },
        function()
          require("various-textobjs").diagnostics()
        end,
        desc = "Diagnostics",
      },
      {
        "iy",
        ft = { "python" },
        mode = { "o", "x" },
        function()
          require("various-textobjs").pyTripleQuotes("inner")
        end,
        desc = "Triple Quotes",
      },
      {
        "ay",
        ft = { "python" },
        mode = { "o", "x" },
        function()
          require("various-textobjs").pyTripleQuotes("outer")
        end,
        desc = "Triple Quotes",
      },
      {
        "iC",
        ft = { "css", "scss", "less" },
        mode = { "o", "x" },
        function()
          require("various-textobjs").cssSelector("inner")
        end,
        desc = "CSS Selector",
      },
      {
        "aC",
        ft = { "css", "scss", "less" },
        mode = { "o", "x" },
        function()
          require("various-textobjs").cssSelector("outer")
        end,
        desc = "CSS Selector",
      },
      {
        "i#",
        ft = { "css", "scss", "less" },
        mode = { "o", "x" },
        function()
          require("various-textobjs").cssColor("inner")
        end,
        desc = "CSS Color",
      },
      {
        "a#",
        ft = { "css", "scss", "less" },
        mode = { "o", "x" },
        function()
          require("various-textobjs").cssColor("outer")
        end,
        desc = "CSS Color",
      },
      {
        "iP",
        ft = { "sh" },
        mode = { "o", "x" },
        function()
          require("various-textobjs").shellPipe("inner")
        end,
        desc = "Pipe",
      },
      {
        "aP",
        ft = { "sh" },
        mode = { "o", "x" },
        function()
          require("various-textobjs").shellPipe("outer")
        end,
        desc = "Pipe",
      },
      {
        "iH",
        ft = { "html, xml, css, scss, less" },
        mode = { "o", "x" },
        function()
          require("various-textobjs").htmlAttribute("inner")
        end,
        desc = "HTML Attribute",
      },
      {
        "iv",
        mode = { "o", "x" },
        function()
          require("various-textobjs").value("inner")
        end,
        desc = "Value",
      },
      {
        "av",
        mode = { "o", "x" },
        function()
          require("various-textobjs").value("outer")
        end,
        desc = "Value",
      },
      {
        "ik",
        mode = { "o", "x" },
        function()
          require("various-textobjs").key("inner")
        end,
        desc = "Key",
      },
      {
        "ak",
        mode = { "o", "x" },
        function()
          require("various-textobjs").key("outer")
        end,
        desc = "Key",
      },
      {
        "L",
        mode = { "o", "x" },
        function()
          require("various-textobjs").url()
        end,
        desc = "Link",
      },
      {
        "iN",
        mode = { "o", "x" },
        function()
          require("various-textobjs").number("inner")
        end,
        desc = "Number",
      },
      {
        "aN",
        mode = { "o", "x" },
        function()
          require("various-textobjs").number("outer")
        end,
        desc = "Number",
      },
    },
  },
}
