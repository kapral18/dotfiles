local select_keymaps = {
  ["aa"] = "@parameter.outer",
  ["ia"] = "@parameter.inner",
  ["af"] = "@function.outer",
  ["if"] = "@function.inner",
  ["ac"] = "@class.outer",
  ["ic"] = "@class.inner",
  ["a/"] = "@comment.outer",
  ["i/"] = "@comment.inner",
  ["a?"] = "@conditional.outer",
  ["i?"] = "@conditional.inner",
  ["a:"] = "@loop.outer",
  ["i:"] = "@loop.inner",
  ["aj"] = "@jsx_attr",
  ["ij"] = "@jsx_attr",
}

local function set_default(option, value)
  local current = vim.api.nvim_get_option_value(option, { scope = "local" })
  if current == nil or current == "" or current == 0 then
    vim.opt_local[option] = value
    return true
  end
  return false
end

return {
  {
    "nvim-treesitter/nvim-treesitter",
    branch = "main",
    version = false,
    lazy = true,
    build = function()
      local TS = require("nvim-treesitter")
      if not TS.get_installed then
        vim.notify("Please restart Neovim and run `:TSUpdate`", vim.log.levels.ERROR)
        return
      end
      local ts_util = require("util.treesitter")
      ts_util.build(function()
        TS.update(nil, { summary = true })
      end)
    end,
    event = { "BufReadPost", "BufNewFile" },
    cmd = {
      "TSUpdate",
      "TSInstall",
      "TSUninstall",
      "TSInstallFromGrammar",
    },
    opts = function(_, opts)
      opts.indent = { enable = true }
      opts.highlight = { enable = true }
      opts.folds = { enable = true }
      opts.ensure_installed = vim.list_extend(opts.ensure_installed or {}, {
        "bash",
        "c",
        "diff",
        "dockerfile",
        "graphql",
        "printf",
        "query",
        "regex",
        "vim",
        "vimdoc",
      })
      return opts
    end,
    config = function(_, opts)
      local TS = require("nvim-treesitter")
      local ts_util = require("util.treesitter")

      ts_util.prefer_bundled_parser("markdown")

      if not TS.get_installed then
        vim.notify("Please update nvim-treesitter", vim.log.levels.ERROR)
        return
      end

      if type(opts.ensure_installed) ~= "table" then
        vim.notify("ensure_installed must be a table", vim.log.levels.ERROR)
        return
      end

      -- Setup treesitter
      TS.setup(opts)
      ts_util.get_installed(true)

      -- Install missing parsers
      local install = vim.tbl_filter(function(lang)
        return not ts_util.have(lang)
      end, opts.ensure_installed or {})

      if #install > 0 then
        ts_util.build(function()
          TS.install(install, { summary = true }):await(function()
            ts_util.get_installed(true)
          end)
        end)
      end

      -- Enable features per filetype
      vim.api.nvim_create_autocmd("FileType", {
        group = vim.api.nvim_create_augroup("treesitter_features", { clear = true }),
        callback = function(ev)
          local ft = ev.match
          local lang = vim.treesitter.language.get_lang(ev.match)

          if not ts_util.have(ft) then
            return
          end

          local function enabled(feat, query)
            local f = opts[feat] or {}
            return f.enable ~= false
              and not (type(f.disable) == "table" and vim.tbl_contains(f.disable, lang))
              and ts_util.have(ft, query)
          end

          -- Highlighting
          if enabled("highlight", "highlights") then
            pcall(vim.treesitter.start, ev.buf)
          end

          -- Indentation
          if enabled("indent", "indents") then
            set_default("indentexpr", "v:lua.require'util.treesitter'.indentexpr()")
          end

          -- Folds
          if enabled("folds", "folds") then
            if set_default("foldmethod", "expr") then
              set_default("foldexpr", "v:lua.require'util.treesitter'.foldexpr()")
            end
          end
        end,
      })
    end,
  },
  {
    "nvim-treesitter/nvim-treesitter-textobjects",
    branch = "main",
    lazy = true,
    event = "VeryLazy",
    opts = {
      select = {
        enable = true,
        lookahead = true,
        include_surrounding_whitespace = true,
        keymaps = select_keymaps,
      },
      move = {
        enable = true,
        keys = {
          goto_next_start = { ["]r"] = "@return.outer" },
          goto_next_end = { ["]R"] = "@return.outer" },
          goto_previous_start = { ["[r"] = "@return.outer" },
          goto_previous_end = { ["[R"] = "@return.outer" },
        },
      },
    },
    keys = function(_, keys)
      local select = {}
      for lhs, query in pairs(select_keymaps) do
        local desc = "Select " .. query:gsub("@", ""):gsub("%.", " "):gsub("^%l", string.upper)
        table.insert(select, {
          lhs,
          function()
            require("nvim-treesitter-textobjects.select").select_textobject(query, "textobjects")
          end,
          mode = { "x", "o" },
          desc = desc,
        })
      end
      vim.list_extend(keys, select)
      return keys
    end,
  },
  {
    "wellle/visual-split.vim",
    event = "VeryLazy",
  },
  {
    "aaronik/treewalker.nvim",
    lazy = true,
    event = "VeryLazy",

    -- The following options are the defaults.
    -- Treewalker aims for sane defaults, so these are each individually optional,
    -- and setup() does not need to be called, so the whole opts block is optional as well.
    opts = {
      -- Whether to briefly highlight the node after jumping to it
      highlight = true,

      -- How long should above highlight last (in ms)
      highlight_duration = 250,

      -- The color of the above highlight. Must be a valid vim highlight group.
      -- (see :h highlight-group for options)
      highlight_group = "CursorLine",
    },

    keys = {
      -- movement
      { "<A-S-k>", "<cmd>Treewalker Up<cr>", mode = { "n", "x" } },
      { "<A-S-j>", "<cmd>Treewalker Down<cr>", mode = { "n", "x" } },
      { "<A-S-l>", "<cmd>Treewalker Right<cr>", mode = { "n", "x" } },
      { "<A-S-h>", "<cmd>Treewalker Left<cr>", mode = { "n", "x" } },

      -- swapping
      { "<C-S-j>", "<cmd>Treewalker SwapDown<cr>" },
      { "<C-S-k>", "<cmd>Treewalker SwapUp<cr>" },
      { "<C-S-l>", "<cmd>Treewalker SwapRight<CR>" },
      { "<C-S-h>", "<cmd>Treewalker SwapLeft<CR>" },
    },
  },
  {
    "nmac427/guess-indent.nvim",
    event = "BufReadPre",
    opts = {},
  },
  {
    "junegunn/vim-easy-align",
    keys = {
      { "<leader>la", "<Plug>(EasyAlign)", mode = { "n", "x" }, desc = "Easy align" },
      { "<leader>lA", "<Plug>(LiveEasyAlign)", mode = { "n", "x" }, desc = "Live Easy align" },
    },
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
    "windwp/nvim-ts-autotag",
    lazy = true,
    event = { "BufReadPost", "BufNewFile" },
    config = function()
      require("nvim-ts-autotag").setup({
        opts = {
          enable_close_on_slash = true, -- Auto close on trailing </
        },
      })
    end,
  },
}
