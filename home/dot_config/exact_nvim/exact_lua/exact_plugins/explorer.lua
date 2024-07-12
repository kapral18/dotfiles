local buf_rename_utils = require("utils.git-mv-buffers")
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

return {
  {
    "nvim-neo-tree/neo-tree.nvim",
    lazy = false,
    dependencies = {
      "ibhagwan/fzf-lua",
    },
    opts = {
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
        follow_current_file = {
          enabled = true,
        },
        use_libuv_file_watcher = true,
      },
      window = {
        mappings = {
          ["<leader>nf"] = "find_in_dir",
          ["<leader>ng"] = "grep_in_dir",
          ["K"] = "focus_parent",
          ["D"] = "diff_files",
          ["r"] = "git_rename",
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
        diff_files = function(state)
          local node = state.tree:get_node()
          local log = require("neo-tree.log")
          state.clipboard = state.clipboard or {}
          if diff_Node and diff_Node ~= tostring(node.id) then
            local current_Diff = node.id
            require("neo-tree.utils").open_file(state, diff_Node, open)
            vim.cmd("vert diffs " .. current_Diff)
            log.info("Diffing " .. diff_Name .. " against " .. node.name)
            diff_Node = nil
            current_Diff = nil
            state.clipboard = {}
            require("neo-tree.ui.renderer").redraw(state)
          else
            local existing = state.clipboard[node.id]
            if existing and existing.action == "diff" then
              state.clipboard[node.id] = nil
              diff_Node = nil
              require("neo-tree.ui.renderer").redraw(state)
            else
              state.clipboard[node.id] = { action = "diff", node = node }
              diff_Name = state.clipboard[node.id].node.name
              diff_Node = tostring(state.clipboard[node.id].node.id)
              log.info("Diff source file " .. diff_Name)
              require("neo-tree.ui.renderer").redraw(state)
            end
          end
        end,
        git_rename = function(state)
          local node = state.tree:get_node()
          if node.type == "message" then
            return
          end

          local cmds = require("neo-tree.sources.filesystem.commands")
          local has_git = vim.fn.finddir(".git", ";") ~= ""

          if not has_git then
            return cmds.rename(state)
          end

          local path = node:get_id()

          if not common_utils.is_git_tracked(path) then
            return cmds.rename(state)
          end

          local name = node.name
          local events = require("neo-tree.events")
          vim.ui.input({ prompt = "New name: " .. name }, function(new_name)
            if new_name == "" or new_name == nil then
              return
            end

            local base_path = vim.fn.fnamemodify(path, ":h")
            local cmd = { "git", "mv", path, base_path .. "/" .. new_name }
            -- Execute the command and handle errors
            local ok, err = pcall(function()
              vim.fn.system(cmd)
            end)
            if not ok then
              print("Error executing command: " .. err)
              return
            end

            vim.schedule(function()
              local main_win_id = buf_rename_utils.get_window_to_right()
              local old_cursor_pos = nil

              if main_win_id ~= nil then
                local bufnr = vim.api.nvim_win_get_buf(main_win_id)
                -- get buf name and check if it is the same as the current one
                if vim.api.nvim_buf_get_name(bufnr) == path then
                  old_cursor_pos = vim.api.nvim_win_get_cursor(main_win_id)
                end
              end

              buf_rename_utils.rename_buffer(path, base_path .. "/" .. new_name)

              if main_win_id ~= nil and old_cursor_pos ~= nil then
                vim.api.nvim_win_set_cursor(main_win_id, old_cursor_pos)
              end

              events.fire_event(events.FILE_RENAMED, {
                source = path,
                destination = base_path .. "/" .. new_name,
              })

              require("gitsigns").refresh()

              events.fire_event(events.GIT_EVENT)
            end)
          end)
        end,
      },
    },
  },
  ---@type LazySpec
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
}
