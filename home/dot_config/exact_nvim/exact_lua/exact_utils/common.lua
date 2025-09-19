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

--- Get the current visual selection as a string
---@return string?, number?, number?
function M.get_visual()
  local start_pos = vim.fn.getpos("v")
  local end_pos = vim.fn.getpos(".")

  if start_pos == nil or end_pos == nil then
    return nil, nil, nil
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

--- Check if the current mode is visual or select mode
---@return boolean
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

--- Copy text to the system clipboard
---@param text string
function M.copy_to_clipboard(text)
  -- Use pbcopy to copy text to the system clipboard
  local handle = io.popen("pbcopy", "w")
  if handle == nil then
    return
  end
  handle:write(text)
  handle:close()
end

--- Check if a file is an image
---@param file_path string
---@return boolean
function M.is_image(file_path)
  -- Use a library or a simple heuristic to detect images
  -- For example, you can use the `file` command to check the file type
  local file_type = io.popen("file -b --mime-type " .. vim.fn.shellescape(file_path)):read("*a")
  return file_type:match("image/%w+")
end

--- Open an image file with the default application
---@param img_path string
---@param fallback function
function M.open_image(img_path, fallback)
  if M.is_image(img_path) then
    -- Open the image file with the default Mac associated application
    io.popen("open " .. vim.fn.shellescape(img_path))
  else
    -- Handle non-image files as needed
    fallback()
  end
end

--- Check if a file exists
---@param file_path string
---@return boolean
function M.file_exists(file_path)
  local stat = vim.uv.fs_stat(file_path)
  return stat and stat.type == "file" or false
end

-- workaround for https://github.com/ibhagwan/fzf-lua/issues/2340#issuecomment-3294232666
local function open_qf_window(opts)
  -- If the current window is a float, we need to find a non-float
  -- window to switch to before opening the quickfix/location list.
  if vim.api.nvim_win_get_config(0).relative ~= "" then
    local fzf_win = require("fzf-lua").win.__SELF()
    local target_win = nil
    -- Prefer the original window that launched fzf-lua
    if
      opts.__CTX
      and vim.api.nvim_win_is_valid(opts.__CTX.winid)
      and vim.api.nvim_win_get_config(opts.__CTX.winid).relative == ""
    then
      target_win = opts.__CTX.winid
    else
      -- Fallback: find the first valid, non-floating, non-fzf window
      for _, win in ipairs(vim.api.nvim_list_wins()) do
        if
          vim.api.nvim_win_is_valid(win)
          and vim.api.nvim_win_get_config(win).relative == ""
          and (not fzf_win or win ~= fzf_win.fzf_winid)
        then
          target_win = win
          break
        end
      end
    end

    if target_win then
      vim.api.nvim_set_current_win(target_win)
    end
  end
  vim.cmd(":copen")
end

--- Get fzf options for files and grep
---@return function
function M.get_fzf_opts()
  return function()
    local rg_opts = M.get_fzf_rg_opts()
    local fd_opts = M.get_fzf_fd_opts()
    local actions = require("fzf-lua").actions
    return {
      defaults = {
        git_icons = false,
        file_icons = false,
        copen = function(sel, opts)
          open_qf_window(opts)
        end,
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
          cmd = "f-bat-preview",
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

--- Get options for fzf rg command
---@return string, string
function M.get_fzf_rg_opts()
  local rg_ignore_glob =
    "-g '!{node_modules,.next,dist,build,reports,tags,.idea,.vscode,.yarn,.nyc_output,__generated__,reports,storybook-static,*.min.js,*.min.css,junit.xml,bazel-*,data,target,.chromium,.es,.yarn-*}'"

  local rg_opts_unrestricted =
    "--column --multiline --line-number --no-heading --color=always --smart-case --max-columns=4096 --hidden --no-ignore -g '!{.git,tsconfig.tsbuildinfo,*.map}'"

  local rg_opts = rg_opts_unrestricted .. " " .. rg_ignore_glob

  return rg_opts, rg_opts_unrestricted
end

--- Get options for fzf fd command
---@return string, string
function M.get_fzf_fd_opts()
  local fd_ignore_glob =
    "-E '{node_modules,.next,dist,build,reports,.idea,.vscode,.yarn,.nyc_output,__generated__,reports,storybook-static}/' -E '{*.min.js,*.min.css,junit.xml,bazel-*,data,target,.chromium,.es,.yarn-*}'"

  local fd_opts_unrestricted =
    "--color=never --type f --hidden --no-ignore --follow -E '{.git,tsconfig.tsbuildinfo,*.map}'"

  local fd_opts = fd_opts_unrestricted .. " " .. fd_ignore_glob

  return fd_opts, fd_opts_unrestricted
end

---@param glob string
---@return string
function M.glob_to_lua_pattern(glob)
  local escaped_glob = vim.pesc(glob)

  -- Handle [! character class negation first
  local partial_pattern = escaped_glob:gsub("%%%[!", "NEGATE_CLASS")

  partial_pattern = partial_pattern:gsub(vim.pesc("%*%*/%*"), "TRIPLE_ASTERISK")
  partial_pattern = partial_pattern:gsub(vim.pesc("%*%*/"), "DOUBLE_ASTERISK_SLASH")
  partial_pattern = partial_pattern:gsub(vim.pesc("%*%*"), "DOUBLE_ASTERISK")
  partial_pattern = partial_pattern:gsub(vim.pesc("%*"), "SINGLE_ASTERISK")
  partial_pattern = partial_pattern:gsub(vim.pesc("%?"), "QUESTION_MARK")

  -- Replace placeholders with Lua patterns
  partial_pattern = partial_pattern:gsub("TRIPLE_ASTERISK", ".*") -- *** matches anything
  partial_pattern = partial_pattern:gsub("DOUBLE_ASTERISK_SLASH", ".*/") -- **/ matches zero or more chars including /
  partial_pattern = partial_pattern:gsub("DOUBLE_ASTERISK", ".*") -- ** matches anything
  partial_pattern = partial_pattern:gsub("SINGLE_ASTERISK", "[^/]*") -- * matches anything except /
  partial_pattern = partial_pattern:gsub("QUESTION_MARK", "[^/]") -- ? matches single char except /

  local pattern = partial_pattern:gsub("NEGATE_CLASS", "[^") -- [! becomes [^

  return pattern
end

--- Get the root directory of the current git repository
---@return string|nil
function M.get_git_root()
  return vim.fs.root(0, ".git")
end

--- Get project root directory
---@return string|nil
function M.get_project_root()
  return vim.fs.root(0, ".git") or vim.env.PWD
end

return M
