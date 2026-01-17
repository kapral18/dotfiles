--- FZF-specific utilities (from utils/common.lua)

local M = {}

local function bin_path(cmd)
  local p = vim.fn.exepath(cmd)
  if type(p) == "string" and p ~= "" then
    return p
  end
  local home_bin = vim.fn.expand("~/bin/" .. cmd)
  if vim.fn.executable(home_bin) == 1 then
    return home_bin
  end
  return cmd
end

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

--- Return `rg` options with ANSI coloring disabled.
--- This is useful when the result lines are post-processed (e.g. split into multiline entries)
--- and we don't want ANSI codes to interfere with parsing.
---@param opts string
---@return string
function M.rg_opts_without_color(opts)
  if type(opts) ~= "string" then
    return ""
  end
  -- `string.gsub` returns (string, count); wrapping to return only the string.
  return (opts:gsub("%-%-color=always", "--color=never"))
end

--- Convert `rg` output lines `file:line:col:text` into multiline, NUL-separated entries:
--- - line 1 (header): `file:line:col:\tfile\tline\tcol`
--- - line 2: match text
--- This allows:
--- - fzf to display wrapped text (`--wrap`) without truncating the real path (hidden fields)
--- - previews/actions to use the hidden tab fields reliably.
---@return string
function M.rg_to_fzf_multiline_tab_fields_pipe()
  -- Uses `f-fzf-rg-multiline` (installed from `home/exact_bin/executable_f-fzf-rg-multiline`).
  -- This avoids embedding an unreadable inline perl one-liner here.
  -- NOTE: do NOT shellescape the command here: fzf-lua already wraps commands,
  -- and nested quoting can prevent the helper from executing (breaking multiline).
  return " | " .. bin_path("f-fzf-rg-multiline")
end

--- Build a native fzf `--preview` command that follows the match line.
--- IMPORTANT: do NOT pass `{}` (the full entry) to the preview command.
--- With `--wrap` + multiline entries, `{}` can be huge and may hit:
---   `fork/exec /bin/sh: argument list too long`
--- Instead, pass only the extracted fields (file + line), which are small.
---@param file_field string fzf placeholder for file field (e.g. "{2}" or "{1}")
---@param line_field string fzf placeholder for line field (e.g. "{3}" or "{2}")
---@return string
function M.fzf_preview_follow_cmd(file_field, line_field)
  -- Use the helper as $0, and pass file/line as $1/$2.
  -- Avoid nested shellescape/quotes for the same reason as above.
  local preview_bin = bin_path("f-fzf-preview-follow")
  return "bash -lc 'exec \"$0\" --file \"$1\" --line \"$2\"' "
    .. preview_bin
    .. " "
    .. file_field
    .. " "
    .. line_field
end

--- Open a grep-like entry (`file:line:col:` or tab-metadata multiline entry).
--- Supports entries produced by `M.rg_to_fzf_multiline_tab_fields_pipe()`.
---@param selected string[]
---@param opts table?
---@param opener? "edit"|"split"|"vsplit"|"tabedit"
function M.open_rg_entry(selected, opts, opener)
  local entry = selected and selected[1]
  if type(entry) ~= "string" or entry == "" then
    return
  end

  local fzf_utils = require("fzf-lua.utils")
  if type(fzf_utils.strip_ansi_coloring) == "function" then
    entry = fzf_utils.strip_ansi_coloring(entry)
  else
    entry = entry:gsub("\27%[[0-9;]*m", "")
  end

  local header = entry:match("([^\n]*)") or entry
  local parts = vim.split(header, "\t", { plain = true })
  local file, line, col

  if #parts >= 4 then
    file = parts[2]
    line = parts[3]
    col = parts[4]
  else
    file, line, col = header:match("^(.-):(%d+):(%d+):")
    if not file then
      file, line = header:match("^(.-):(%d+):")
    end
  end

  if not file or file == "" then
    return
  end

  local cwd = (opts and opts.cwd) or vim.uv.cwd()
  local path = file
  if type(path) == "string" and path:sub(1, 1) ~= "/" then
    local base = type(cwd) == "string" and cwd or ""
    base = base:gsub("/$", "")
    path = base .. "/" .. path
  end

  opener = opener or "edit"
  vim.cmd(opener .. " " .. vim.fn.fnameescape(path))

  local lnum = tonumber(line)
  local cnum = tonumber(col) or 1
  if lnum then
    pcall(vim.api.nvim_win_set_cursor, 0, { lnum, math.max(cnum - 1, 0) })
  end
end

--- Actions table for grep-like entries that open the selected match.
---@return table
function M.grep_entry_actions()
  return {
    ["default"] = function(selected, opts)
      M.open_rg_entry(selected, opts, "edit")
    end,
    ["enter"] = function(selected, opts)
      M.open_rg_entry(selected, opts, "edit")
    end,
    ["ctrl-s"] = function(selected, opts)
      M.open_rg_entry(selected, opts, "split")
    end,
    ["ctrl-v"] = function(selected, opts)
      M.open_rg_entry(selected, opts, "vsplit")
    end,
    ["ctrl-t"] = function(selected, opts)
      M.open_rg_entry(selected, opts, "tabedit")
    end,
  }
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
        copen = function(_, opts)
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
        ["--wrap"] = true,
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
        fzf_opts = {
          ["--ansi"] = false,
          ["--wrap"] = true,
          ["--preview"] = "f-bat-preview {} --style=numbers --line-range :300 --color always",
        },
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
        fzf_opts = {
          ["--delimiter"] = ":",
          ["--wrap"] = true,
          ["--preview"] = M.fzf_preview_follow_cmd("{1}", "{2}"),
        },
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
        -- fzf-lua uses `vim.lsp.buf_request_sync` for many LSP pickers; TS projects can
        -- legitimately take longer than the default 5s to respond (esp. cold tsserver).
        async_or_timeout = 15000,
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
