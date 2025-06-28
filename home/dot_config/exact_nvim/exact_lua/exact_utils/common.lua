local M = {}

-- show confirm input
--@param message string
--@param callback function
M.confirm = function(message, callback)
  local opts = {
    prompt = message .. " y/n: ",
  }
  vim.ui.input(opts, function(value)
    callback(value == "y" or value == "Y")
  end)
end

function M.get_visual()
  local start_pos = vim.fn.getpos("v")
  local end_pos = vim.fn.getpos(".")

  if start_pos == nil or end_pos == nil then
    return ""
  end

  local start_row, start_col = start_pos[2], start_pos[3]
  local end_row, end_col = end_pos[2], end_pos[3]

  if end_row < start_row then
    start_row, end_row = end_row, start_row
  end
  if end_col < start_col then
    start_col, end_col = end_col, start_col
  end

  local lines = vim.api.nvim_buf_get_text(0, start_row - 1, start_col - 1, end_row - 1, end_col, {})

  return table.concat(lines, "\n"), start_row, end_row
end

function M.in_visual()
  local modes = {
    Rv = true,
    Rvc = true,
    Rvx = true,
    V = true,
    Vs = true,
    niV = true,
    noV = true,
    nov = true,
    v = true,
    vs = true,
  }
  local current_mode = vim.api.nvim_get_mode()["mode"]
  return modes[current_mode]
end

function M.copy_to_clipboard(text)
  -- Use pbcopy to copy text to the system clipboard
  local handle = io.popen("pbcopy", "w")
  if handle == nil then
    return
  end
  handle:write(text)
  handle:close()
end

function M.is_image(file_path)
  -- Use a library or a simple heuristic to detect images
  -- For example, you can use the `file` command to check the file type
  local file_type = io.popen("file -b --mime-type " .. vim.fn.shellescape(file_path)):read("*a")
  return file_type:match("image/%w+")
end

function M.open_image(img_path, fallback)
  if M.is_image(img_path) then
    -- Open the image file with the default Mac associated application
    io.popen("open " .. vim.fn.shellescape(img_path))
  else
    -- Handle non-image files as needed
    fallback()
  end
end

function M.file_exists(file_path)
  local stat = vim.uv.fs_stat(file_path)
  return stat and stat.type == "file" or false
end

function M.get_fzf_opts()
  return function()
    local rg_opts = M.get_fzf_rg_opts()
    local fd_opts = M.get_fzf_fd_opts()
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
        rg_opts = rg_opts,
        fd_opts = fd_opts,
        fzf_opts = { ["--ansi"] = false },
        actions = {
          ["default"] = M.fzf_open_file,
          ["enter"] = M.fzf_open_file,
          ["ctrl-q"] = actions.file_sel_to_qf,
          ["ctrl-y"] = function(selected)
            M.copy_to_clipboard(selected[1])
          end,
          -- we don't need alt-i, as it's covered by ctrl-g
          ["alt-h"] = { actions.toggle_hidden },
        },
      },
      grep = {
        previewer = "bat",
        multiline = 2,
        prompt = "Live Grep❯ ",
        input_prompt = "Grep❯ ",
        rg_opts = rg_opts,
        actions = {
          ["ctrl-q"] = actions.file_sel_to_qf,
          ["ctrl-y"] = function(selected)
            M.copy_to_clipboard(selected[1])
          end,
          -- we need alt-i as ctrl-g is used for cycling search patterns
          ["alt-i"] = { actions.toggle_ignore },
          ["alt-h"] = { actions.toggle_hidden },
        },
      },
      lsp = {
        multiline = 2,
      },
    }
  end
end

function M.fzf_open_file(selected, opts)
  M.open_image(selected[1], function()
    require("fzf-lua.actions").file_edit(selected, opts)
  end)
end

function M.get_fzf_rg_opts()
  local rg_ignore_glob =
    "-g '!{node_modules,.next,dist,build,reports,tags,.idea,.vscode,.yarn,.nyc_output,__generated__,reports,storybook-static,*.min.js,*.min.css,junit.xml,bazel-*,data,target,.buildkite,.chromium,.es,.yarn-*}'"

  local rg_opts_unrestricted =
    "--column --multiline --line-number --no-heading --color=always --smart-case --max-columns=4096 --hidden --no-ignore -g '!{.git,tsconfig.tsbuildinfo,*.map}'"

  local rg_opts = rg_opts_unrestricted .. " " .. rg_ignore_glob

  return rg_opts, rg_opts_unrestricted
end

function M.get_fzf_fd_opts()
  local fd_ignore_glob =
    "-E '{node_modules,.next,dist,build,reports,.idea,.vscode,.yarn,.nyc_output,__generated__,reports,storybook-static}/' -E '{*.min.js,*.min.css,junit.xml,bazel-*,data,target,.buildkite,.chromium,.es,.yarn-*}'"

  local fd_opts_unrestricted =
    "--color=never --type f --hidden --no-ignore --follow -E '{.git,tsconfig.tsbuildinfo,*.map}'"

  local fd_opts = fd_opts_unrestricted .. " " .. fd_ignore_glob

  return fd_opts, fd_opts_unrestricted
end

return M
