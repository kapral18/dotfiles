---@module "lazy"
---@module "yazi"

local common_utils = require("utils.common")

local winopts = {
  large = {
    vertical = {
      height = 0.9,
      width = 0.9,
      preview = {
        layout = "vertical",
        vertical = "up:65%",
      },
    },
  },
}

local function safe_open(action)
  return function(state)
    local node = state.tree:get_node()
    local full_path = node:get_id()
    common_utils.open_image(full_path, function()
      require("neo-tree.sources.filesystem.commands")[action](state)
    end)
  end
end

---@type LazySpec
return {
  {
    "nvim-neo-tree/neo-tree.nvim",
    lazy = false,
    dependencies = {
      "ibhagwan/fzf-lua",
    },
    keys = {
      {
        "<leader>e",
        function()
          require("neo-tree.command").execute({ toggle = true, dir = vim.uv.cwd(), reveal = true, no_wait = true })
        end,
        desc = "Explorer NeoTree (cwd)",
      },
      {
        "<leader>ge",
        function()
          require("neo-tree.command").execute({ source = "git_status", toggle = true, dir = vim.uv.cwd() })
        end,
        desc = "Git Explorer NeoTree (cwd)",
      },
    },
    opts = {
      default_component_configs = {
        file_size = {
          enabled = false,
        },
        type = {
          enabled = false,
        },
        last_modified = {
          enabled = false,
        },
      },
      filesystem = {
        filtered_items = {
          visible = true, -- when true, they will just be displayed differently than normal items
          hide_dotfiles = false,
          hide_gitignored = false,
          hide_hidden = false, -- only works on Windows for hidden files/directories
          hide_by_name = {
            --"node_modules",
          },
          hide_by_pattern = {
            --"*.meta",
            --"*/src/*/tsconfig.json",
          },
          always_show = { -- remains visible even if other settings would normally hide it
            --".gitignored",
          },
          never_show = { -- remains hidden even if visible is toggled to true, this overrides always_show
            --".DS_Store",
            --"thumbs.db",
          },
          never_show_by_pattern = { -- uses glob style patterns
            --".null-ls_*",
          },
        },
      },
      window = {
        position = "float",
        width = 50,
        mappings = {
          ["<leader>nf"] = "find_in_dir",
          ["<leader>ng"] = "grep_in_dir",
          ["K"] = "focus_parent",
          ["D"] = "diff_files",
          [";"] = "open_in_oil",
          ["<2-leftmouse>"] = safe_open("open"),
          ["<cr>"] = safe_open("open"),
          ["S"] = safe_open("open_split"),
          ["l"] = safe_open("open"),
          ["s"] = safe_open("open_vsplit"),
          ["t"] = safe_open("open_tabnew"),
          ["w"] = safe_open("open_with_window_picker"),
        },
      },
      commands = {
        find_in_dir = function(state)
          local node = state.tree:get_node()
          local path = node:get_id()
          require("fzf-lua").files({ cwd = path, winopts = winopts.large.vertical })
        end,
        grep_in_dir = function(state)
          local node = state.tree:get_node()
          local path = node:get_id()
          require("fzf-lua").live_grep({ cwd = path, winopts = winopts.large.vertical })
        end,
        focus_parent = function(state)
          local node = state.tree:get_node()
          require("neo-tree.ui.renderer").focus_node(state, node:get_parent_id())
        end,
        open_in_oil = function(state)
          local node = state.tree:get_node()
          local path = node:get_id()

          -- make sure it's a directory
          if vim.fn.isdirectory(path) == 0 then
            return
          end
          require("oil").open_float(path)
        end,
        diff_files = function(state)
          local node = state.tree:get_node()
          if node.type ~= "file" then
            return
          end

          state.clipboard = state.clipboard or {}

          if not state.__current_diff_node__ then
            state.__current_diff_node__ = node
            state.clipboard[node.id] = { action = "diff", node = node }
          else
            local first_file = state.clipboard[state.__current_diff_node__.id].node.path
            local second_file = node.path

            vim.cmd("tabnew " .. vim.fn.fnameescape(first_file))
            vim.cmd("vertical diffsplit " .. vim.fn.fnameescape(second_file))

            local cleanup_and_close = function()
              vim.cmd("diffoff!")
              vim.cmd("tabclose")
            end

            vim.keymap.set("n", "q", cleanup_and_close, {
              buffer = true,
              silent = true,
              noremap = true,
              desc = "Clear diff and close tab",
            })

            -- Clear the diff source
            state.clipboard[node.id] = nil
            state.clipboard[state.__current_diff_node__.id] = nil
            state.__current_diff_node__ = nil
          end

          require("neo-tree.ui.renderer").redraw(state)
        end,
      },
    },
  },
  {
    "mikavilpas/yazi.nvim",
    event = "VeryLazy",
    keys = {
      -- 👇 in this section, choose your own keymappings!
      {
        "<leader>ye",
        function()
          require("yazi").yazi()
        end,
        desc = "Open the file manager",
      },
      {
        -- Open in the current working directory
        "<leader>yw",
        function()
          require("yazi").yazi(nil, vim.fn.getcwd())
        end,
        desc = "Open the file manager in nvim's working directory",
      },
    },
    ---@type YaziConfig
    opts = {
      -- if you want to open yazi instead of netrw, see below for more info
      open_for_directories = false,
    },
  },
  {
    "stevearc/oil.nvim",
    dependencies = { { "echasnovski/mini.icons", opts = {} } },
    opts = {
      default_file_explorer = true,
      delete_to_trash = true,
      keymaps = {
        ["q"] = "actions.close",
      },
      lsp_file_methods = {
        autosave_changes = true,
      },
      watch_for_changes = true,
      view_options = {
        show_hidden = true,
      },
    },
    keys = {
      {
        "<leader>;",
        function()
          require("oil").toggle_float()
        end,
        desc = "Toggle oil",
      },
    },
  },
}
