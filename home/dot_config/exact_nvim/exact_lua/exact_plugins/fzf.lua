local common_utils = require("utils.common")

local function open_file(selected, opts)
  common_utils.open_image(selected[1], function()
    require("fzf-lua.actions").file_edit(selected, opts)
  end)
end

local function get_fzf_fn(cmd, opts)
  opts = opts or {}
  return function()
    require("fzf-lua")[cmd](opts)
  end
end

local function get_telescope_fn(cmd, opts)
  opts = opts or {}
  return function()
    require("telescope.builtin")[cmd](opts)
  end
end

local function live_grep_with_patterns(initial_search, opts)
  local search_patterns = {
    initial_search,
    [[\b]]
      .. initial_search
      .. [[\b -- **/*.ts **/*.tsx !*.d.ts !*.test.ts !*.test.tsx !**/__mocks__/* !**/__jest__/* !**/fixtures/* !**/test/* !**/mock/*]],
    [[\b]] .. initial_search .. [[\b -- **/*.ts **/*.tsx !*.d.ts]],
  }
  local current_index = 1

  local function cycle_current_index()
    current_index = (current_index % #search_patterns) + 1
  end

  local function nested_live_grep()
    require("fzf-lua").live_grep(vim.tbl_deep_extend("force", {
      rg_glob = true,
      no_esc = true,
      actions = {
        ["ctrl-g"] = { nested_live_grep }, -- No need to pass rg_opts here
      },
      search = search_patterns[current_index],
      ["keymap.fzf.start"] = "beginning-of-line+forward-char+forward-char",
    }, opts))

    cycle_current_index()
  end

  nested_live_grep()
end

return {
  {
    "ibhagwan/fzf-lua",
    dependencies = {
      { "nvim-tree/nvim-web-devicons" },
      { "nvim-telescope/telescope.nvim" },
      {
        "leath-dub/snipe.nvim",
        opts = {
          navigate = {
            cancel_snipe = "q",
          },
        },
      },
    },
    keys = {
      {
        "<leader>,",
        false,
      },
      {
        "<leader>sb",
        function()
          require("snipe").open_buffer_menu()
        end,
        desc = "Open Snipe buffer menu",
      },
      { "<leader>:", "<cmd>Telescope command_history<cr>", desc = "Command History" },
      {
        "<leader><space>",
        get_fzf_fn("files", {
          cwd = vim.uv.cwd(),
        }),
        desc = "Files",
      },
      {
        "<leader>i",
        get_fzf_fn("files", {
          cwd = vim.uv.cwd(),
        }),
        desc = "Files",
      },
      { "<leader>fr", get_fzf_fn("oldfiles", {
        cwd = vim.uv.cwd(),
      }), desc = "Recent (cwd)" },
      { "<leader>fr", get_telescope_fn("oldfiles", { cwd = vim.uv.cwd() }), desc = "Recent (cwd)" },
      { "<leader>fR", "<cmd>Telescope oldfiles<cr>", desc = "Recent (all)" },
      {
        "<leader>/",
        get_fzf_fn("lgrep_curbuf"),
        desc = "Grep",
      },
      {
        "<leader>sg",
        function()
          live_grep_with_patterns("", { cwd = vim.uv.cwd() })
        end,
        desc = "Live Grep",
      },
      {
        "<leader>sG",
        function()
          live_grep_with_patterns("", { cwd = vim.uv.cwd() })
        end,
        desc = "Live Grep (+ ignored)",
      },
      {
        "<leader>sR",
        get_fzf_fn("resume"),
        desc = "Resume Picker List",
      },
      {
        "<leader>sw",
        function()
          live_grep_with_patterns(vim.fn.expand("<cword>"), {
            cwd = vim.uv.cwd(),
          })
        end,
        desc = "Live Grep CWord",
      },
      {
        "<leader>sW",
        function()
          live_grep_with_patterns(vim.fn.expand("<cword>"), {
            cwd = vim.uv.cwd(),
          })
        end,
        desc = "Live Grep CWord (+ ignored)",
      },
      {
        "<leader>sw",
        function()
          live_grep_with_patterns(vim.trim(require("fzf-lua").utils.get_visual_selection()), {
            no_esc = false,
            cwd = vim.uv.cwd(),
          })
        end,
        mode = "v",
        desc = "Live Grep Selection",
      },
      {
        "<leader>sW",
        function()
          live_grep_with_patterns(vim.trim(require("fzf-lua").utils.get_visual_selection()), {
            no_esc = false,
            cwd = vim.uv.cwd(),
          })
        end,
        mode = "v",
        desc = "Live Grep Selection (+ignored)",
      },
    },
    opts = function()
      local actions = require("fzf-lua").actions
      return {
        defaults = {
          git_icons = false,
          file_icons = false,
        },
        winopts = {
          height = 0.50,
          width = 0.75,
          fullscreen = true,
          preview = {
            default = "builtin",
            border = "noborder",
            wrap = "wrap",
            layout = "vertical",
            vertical = "up:75%",
            scrollbar = false,
            scrollchars = { "", "" },
            winopts = {
              number = false,
              relativenumber = false,
            },
          },
        },
        keymap = {
          fzf = {
            ["down"] = "down",
            ["up"] = "up",
            ["ctrl-c"] = "abort",
            ["ctrl-a"] = "toggle-all",
            ["ctrl-q"] = "select-all+accept",
            ["ctrl-d"] = "preview-page-down",
            ["ctrl-u"] = "preview-page-up",
          },
        },
        fzf_opts = {
          ["--prompt"] = "  ",
          ["--keep-right"] = false,
          ["--preview"] = "bat --style=numbers --line-range :300 --color always {}",
        },
        previewers = {
          bat = {
            cmd = "bat-preview",
            -- set a bat theme, `bat --list-themes`
            theme = "Catppuccin-mocha",
          },
        },
        files = {
          previewer = "bat",
          prompt = "Files❯ ",
          fzf_opts = { ["--ansi"] = false },
          actions = {
            ["default"] = open_file,
            ["enter"] = open_file,
            ["ctrl-q"] = actions.file_sel_to_qf,
            ["ctrl-y"] = function(selected)
              common_utils.copy_to_clipboard(selected[1])
            end,
            -- we don't need alt-i, as it's covered by ctrl-g
            ["alt-h"] = { actions.toggle_hidden },
          },
        },
        grep = {
          previewer = "bat",
          prompt = "Live Grep❯ ",
          input_prompt = "Grep❯ ",
          actions = {
            ["ctrl-q"] = actions.file_sel_to_qf,
            ["ctrl-y"] = function(selected)
              common_utils.copy_to_clipboard(selected[1])
            end,
            -- we need alt-i as ctrl-g is used for cycling search patterns
            ["alt-i"] = { actions.toggle_ignore },
            ["alt-h"] = { actions.toggle_hidden },
          },
        },
      }
    end,
  },
}
