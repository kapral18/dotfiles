return {
  {
    "nvim-treesitter/nvim-treesitter-context",
    enabled = false,
  },
  {
    "nvim-treesitter/nvim-treesitter-textobjects",
    lazy = true,
    dependencies = {
      "nvim-treesitter/nvim-treesitter",
      opts = function(_, opts)
        opts.highlight = {
          enable = true,
          use_languagetree = true,
        }
        opts.indent = { enable = true }
        opts.playground = { enable = true }
        opts.autotag = { enable = true }
        opts.incremental_selection = {
          enable = true,
          keymaps = {
            init_selection = "<Enter>",
            node_incremental = "<Enter>",
            node_decremental = "<BS>",
          },
        }
        opts.textobjects = { --{{{
          select = { -- {{{
            enable = true,
            keymaps = {
              ["aC"] = "@class.outer",
              ["aa"] = "@parameter.outer",
              ["ab"] = "@block.outer",
              ["ac"] = "@conditional.outer",
              ["ad"] = "@comment.outer",
              ["ae"] = "@block.outer",
              ["af"] = "@function.outer",
              ["ak"] = "@assignment.lhs",
              ["al"] = "@loop.outer",
              ["am"] = "@call.outer",
              ["as"] = "@statement.outer",
              ["au"] = "@call.outer",
              ["av"] = "@assignment.rhs",
              ["iC"] = "@class.inner",
              ["ia"] = "@parameter.inner",
              ["ib"] = "@block.inner",
              ["ic"] = "@conditional.inner",
              ["ie"] = "@block.inner",
              ["if"] = "@function.inner",
              ["ik"] = "@assignment.lhs",
              ["il"] = "@loop.inner",
              ["im"] = "@call.inner",
              ["is"] = "@statement.inner",
              ["iu"] = "@call.inner",
              ["iv"] = "@assignment.rhs",
            },
          }, --}}}

          move = { --{{{
            enable = true,
            set_jumps = true,
            goto_next_start = {
              ["]f"] = { query = "@function.outer", desc = "Go to start of the next function" },
              ["]b"] = { query = "@block.outer", desc = "Go to start of the next block" },
              ["]gc"] = { query = "@comment.outer", desc = "Go to start of the next comment" },
              ["]a"] = { query = "@parameter.inner", desc = "Go to start of the next parameter" },
              ["]o"] = { query = "@loop.*", desc = "Go to the next loop" },
              ["]s"] = {
                query = "@scope",
                query_group = "locals",
                desc = "Go to the next scope",
              },
            },
            goto_next_end = {
              ["]F"] = { query = "@function.outer", desc = "Go to end of the next function" },
              ["]B"] = { query = "@block.outer", desc = "Go to end of the next block" },
              ["]A"] = { query = "@parameter.outer", desc = "Go to end of the next parameter" },
            },
            goto_previous_start = {
              ["[f"] = { query = "@function.outer", desc = "Go to start of the previous function" },
              ["[b"] = { query = "@block.outer", desc = "Go to start of the previous block" },
              ["[gc"] = { query = "@comment.outer", desc = "Go to start of the previous comment" },
              ["[a"] = { query = "@parameter.inner", desc = "Go to start of the previous parameter" },
              ["[o"] = { query = "@loop.*", desc = "Go to the previous loop" },
              ["[s"] = {
                query = "@scope",
                query_group = "locals",
                desc = "Go to the previous scope",
              },
            },
            goto_previous_end = {
              ["[F"] = { query = "@function.outer", desc = "Go to end of the previous function" },
              ["[B"] = { query = "@block.outer", desc = "Go to end of the previous block" },
              ["[A"] = { query = "@parameter.outer", desc = "Go to end of the previous parameter" },
            },
          }, --}}}

          swap = { --{{{
            enable = true,
            swap_next = {
              ["<leader>.f"] = {
                query = "@function.outer",
                desc = "Swap around with the next function",
              },
              ["<leader>.e"] = { query = "@element", desc = "Swap with the next element" },
              ["<leader>.a"] = { query = "@parameter.inner", desc = "Swap with the next parameter" },
            },
            swap_previous = {
              ["<leader>,f"] = {
                query = "@function.outer",
                desc = "Swap around with the previous function",
              },
              ["<leader>,e"] = { query = "@element", desc = "Swap with the previous element" },
              ["<leader>,a"] = {
                query = "@parameter.inner",
                desc = "Swap with the previous parameter",
              },
            },
          }, --}}}

          lsp_interop = { --{{{
            enable = true,
            peek_definition_code = {
              ["<leader>df"] = { query = "@function.outer", desc = "Peek function definition" },
            },
          }, --}}}
        } -- }}}
      end,
    },
  },
  {
    "chrisgrieser/nvim-various-textobjs",
    opts = { useDefaultKeymaps = true },
    config = function(_, opts)
      require("various-textobjs").setup(opts)
    end,
    event = "VeryLazy",
  },
}
