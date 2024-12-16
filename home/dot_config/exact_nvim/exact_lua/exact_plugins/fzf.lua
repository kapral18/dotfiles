local function copy_to_clipboard(text)
  -- Use pbcopy to copy text to the system clipboard
  local handle = io.popen("pbcopy", "w")
  if handle == nil then
    return
  end
  handle:write(text)
  handle:close()
end

local function is_image(file_path)
  -- Use a library or a simple heuristic to detect images
  -- For example, you can use the `file` command to check the file type
  local file_type = io.popen("file -b --mime-type " .. file_path):read("*a")
  return file_type:match("image/%w+")
end

local function open_file(selected, opts)
  local file_path = selected[1]
  if is_image(file_path) then
    -- Open the image file with the default Mac associated application
    io.popen("open " .. file_path)
  else
    -- Handle non-image files as needed
    require("fzf-lua").actions.file_edit(selected, opts)
  end
end

local function get_fzf_fn(cmd, opts)
  opts = opts or {}
  return function()
    require("fzf-lua")[cmd](opts)
  end
end

local rg_ignore_glob =
  "-g '!{node_modules,.next,dist,build,reports,.idea,.vscode,.yarn,.nyc_output,__generated__,reports,storybook-static,*.min.js,*.min.css,junit.xml,bazel-*,data,target,.buildkite,.chromium,.es,.yarn-*}'"
local fd_ignore_glob =
  "-E '{node_modules,.next,dist,build,reports,.idea,.vscode,.yarn,.nyc_output,__generated__,reports,storybook-static}/' -E '{*.min.js,*.min.css,junit.xml,bazel-*,data,target,.buildkite,.chromium,.es,.yarn-*}'"

local rg_opts_unrestricted =
  "--column --line-number --no-heading --color=always --smart-case --max-columns=4096 --hidden --no-ignore -g '!{.git,tsconfig.tsbuildinfo,*.map}'"

local rg_opts = rg_opts_unrestricted .. " " .. rg_ignore_glob

local fd_opts_unrestricted =
  "--color=never --type f --hidden --no-ignore --follow -E '{.git,tsconfig.tsbuildinfo,*.map}'"

local fd_opts = fd_opts_unrestricted .. " " .. fd_ignore_glob

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
    dependencies = { "nvim-tree/nvim-web-devicons" },
    keys = {
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
          fd_opts = fd_opts_unrestricted,
          cwd = vim.uv.cwd(),
        }),
        desc = "Files",
      },
      {
        "<leader>/",
        get_fzf_fn("lgrep_curbuf"),
        desc = "Grep",
      },
      {
        "<leader>sg",
        function()
          live_grep_with_patterns("", { rg_opts = rg_opts, cwd = vim.uv.cwd() })
        end,
        desc = "Live Grep",
      },
      {
        "<leader>sG",
        function()
          live_grep_with_patterns("", { rg_opts = rg_opts_unrestricted, cwd = vim.uv.cwd() })
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
            rg_opts = rg_opts,
            cwd = vim.uv.cwd(),
          })
        end,
        desc = "Live Grep CWord",
      },
      {
        "<leader>sW",
        function()
          live_grep_with_patterns(vim.fn.expand("<cword>"), {
            rg_opts = rg_opts_unrestricted,
            cwd = vim.uv.cwd(),
          })
        end,
        desc = "Live Grep CWord (+ ignored)",
      },
      {
        "<leader>sw",
        function()
          live_grep_with_patterns(vim.trim(require("fzf-lua").utils.get_visual_selection()), {
            rg_opts = rg_opts .. " --multiline",
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
            rg_opts = rg_opts_unrestricted .. " --multiline",
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
            cmd = "bat_preview",
            -- set a bat theme, `bat --list-themes`
            theme = "Catppuccin-mocha",
          },
        },
        files = {
          previewer = "bat",
          prompt = "Files❯ ",
          rg_opts = rg_opts,
          fd_opts = fd_opts,
          fzf_opts = { ["--ansi"] = false },
          actions = {
            ["enter"] = open_file,
            ["ctrl-q"] = actions.file_sel_to_qf,
            ["ctrl-y"] = function(selected)
              copy_to_clipboard(selected[1])
            end,
            -- we don't need alt-i, as it's covered by ctrl-g
            ["alt-h"] = { actions.toggle_hidden },
          },
        },
        grep = {
          previewer = "bat",
          prompt = "Live Grep❯ ",
          input_prompt = "Grep❯ ",
          rg_opts = rg_opts,
          actions = {
            ["ctrl-q"] = actions.file_sel_to_qf,
            ["ctrl-y"] = function(selected)
              copy_to_clipboard(selected[1])
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
