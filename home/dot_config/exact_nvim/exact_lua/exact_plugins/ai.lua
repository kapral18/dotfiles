return {
  {
    "jackMort/ChatGPT.nvim",
    event = "VeryLazy",
    config = function(_, opts)
      require("chatgpt").setup(opts)
      require("which-key").register({
        ["<leader>o"] = {
          name = "OpenAI's ChatGPT",
          c = { "<cmd>ChatGPT<CR>", "ChatGPT" },
          e = { "<cmd>ChatGPTEditWithInstruction<CR>", "Edit with instruction", mode = { "n", "v" } },
          g = { "<cmd>ChatGPTRun grammar_correction<CR>", "Grammar Correction", mode = { "n", "v" } },
          t = { "<cmd>ChatGPTRun translate<CR>", "Translate", mode = { "n", "v" } },
          k = { "<cmd>ChatGPTRun keywords<CR>", "Keywords", mode = { "n", "v" } },
          d = { "<cmd>ChatGPTRun docstring<CR>", "Docstring", mode = { "n", "v" } },
          a = { "<cmd>ChatGPTRun add_tests<CR>", "Add Tests", mode = { "n", "v" } },
          o = { "<cmd>ChatGPTRun optimize_code<CR>", "Optimize Code", mode = { "n", "v" } },
          s = { "<cmd>ChatGPTRun summarize<CR>", "Summarize", mode = { "n", "v" } },
          f = { "<cmd>ChatGPTRun fix_bugs<CR>", "Fix Bugs", mode = { "n", "v" } },
          x = { "<cmd>ChatGPTRun explain_code<CR>", "Explain Code", mode = { "n", "v" } },
          r = { "<cmd>ChatGPTRun roxygen_edit<CR>", "Roxygen Edit", mode = { "n", "v" } },
          l = { "<cmd>ChatGPTRun code_readability_analysis<CR>", "Code Readability Analysis", mode = { "n", "v" } },
        },
      })
    end,
    opts = {
      openai_params = {
        model = "gpt-4-turbo-preview",
        max_tokens = 4096,
        temperature = 0.1,
      },
      openai_edit_params = {
        model = "gpt-4-turbo-preview",
      },
    },
    dependencies = {
      "MunifTanjim/nui.nvim",
      "nvim-lua/plenary.nvim",
      "nvim-telescope/telescope.nvim",
      "folke/which-key.nvim",
    },
  },
  {
    "David-Kunz/gen.nvim",
    event = "VeryLazy",
    opts = {
      model = "magicoder",
      display_mode = "float",
      show_model = true,
    },
    dependencies = {
      "folke/which-key.nvim",
    },
    config = function(_, opts)
      require("gen").setup(opts)
      require("which-key").register({
        ["<leader>oM"] = {
          name = "Gen.nvim",
          m = { "<cmd>Gen<CR>", "[AI] Gen: Menu", mode = { "n", "x" } },
          s = {
            '<cmd>lua require("gen").select_model()<CR>',
            "[AI] Gen: Select model",
            mode = { "n" },
          },
        },
      })
    end,
  },
  {
    "dustinblackman/oatmeal.nvim",
    event = "VeryLazy",
    cmd = { "Oatmeal" },
    dependencies = {
      "folke/which-key.nvim",
    },
    opts = {
      backend = "ollama",
      model = "phind-codellama:latest",
    },
    config = function(_, opts)
      require("oatmeal").setup(opts)
      require("which-key").register({
        ["<leader>om"] = { "<cmd>Oatmeal<CR>", "[AI] Oatmeal: toggle", mode = { "n", "x" } },
      })
    end,
  },
  {
    "zbirenbaum/copilot.lua",
    event = "InsertEnter",
    opts = {
      filetypes = {
        ["*"] = true,
      },
    },
  },
  -- Use your favorite package manager to install, for example in lazy.nvim
  --  Optionally, you can also install nvim-telescope/telescope.nvim to use some search functionality.
  {
    "sourcegraph/sg.nvim",
    dependencies = {
      "nvim-lua/plenary.nvim", --[[ "nvim-telescope/telescope.nvim ]]
    },

    -- If you have a recent version of lazy.nvim, you don't need to add this!
    build = "nvim -l build/init.lua",
  },
  {
    "hrsh7th/nvim-cmp",
    dependencies = {
      "sourcegraph/sg.nvim",
      opts = {},
    },
    opts = function(_, opts)
      local cmp = require("cmp")
      opts.sources = cmp.config.sources(vim.list_extend(opts.sources, {
        { name = "cody" },
        { name = "nvim_lsp" },
      }))
    end,
  },
}
