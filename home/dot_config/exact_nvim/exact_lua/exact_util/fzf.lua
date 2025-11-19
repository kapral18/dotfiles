--- FZF-specific utilities (from utils/common.lua)

local M = {}

-- workaround for https://github.com/ibhagwan/fzf-lua/issues/2340#issuecomment-3294232666
local RG_BASE_OPTS = table.concat({
  "--column",
  "--multiline",
  "--line-number",
  "--no-heading",
  "--color=always",
  "--smart-case",
  "--max-columns=4096",
  "--hidden",
}, " ")

local RG_OPTS_DEFAULT = RG_BASE_OPTS .. " --glob '!.git/**'"
local RG_OPTS_UNRESTRICTED = RG_BASE_OPTS .. " --no-ignore"

local FD_BASE_OPTS = table.concat({
  "--color=never",
  "--type f",
  "--hidden",
  "--follow",
}, " ")

local FD_OPTS_DEFAULT = FD_BASE_OPTS .. " --exclude .git"
local FD_OPTS_UNRESTRICTED = FD_BASE_OPTS .. " --no-ignore"

M.rg_opts = RG_OPTS_DEFAULT
M.rg_opts_unrestricted = RG_OPTS_UNRESTRICTED
M.fd_opts = FD_OPTS_DEFAULT
M.fd_opts_unrestricted = FD_OPTS_UNRESTRICTED

local function open_qf_window(opts)
  -- If the current window is a float, we need to find a non-float
  -- window to switch to before opening the quickfix/location list.
  if vim.api.nvim_win_get_config(0).relative ~= "" then
    local fzf_win = require("fzf-lua").win.__SELF()
    local target_win = nil
    -- Prefer the original window that launched fzf-lua
    if
      opts.__CTX
      and type(opts.__CTX.winid) == "number"
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

--- Copy text to the system clipboard
---@param text string
--- Copy text to clipboard using pbcopy
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

--- FZF open file handler (supports image preview)
function M.open_file(selected, opts)
  M.open_image(selected[1], function()
    require("fzf-lua.actions").file_edit(selected, opts)
  end)
end

--- Get fzf options for files and grep
---@return function
function M.get_opts()
  return function()
    local rg_opts = M.rg_opts
    local fd_opts = M.fd_opts
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
        ["--prompt"] = "  ",
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
          ["default"] = M.open_file,
          ["enter"] = M.open_file,
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

--- Get options for fzf rg command
---@return string, string
function M.get_rg_opts()
  return M.rg_opts, M.rg_opts_unrestricted
end

--- Get options for fzf fd command
---@return string, string
function M.get_fd_opts()
  return M.fd_opts, M.fd_opts_unrestricted
end

return M
