local fs_util = require("util.fs")

local M = {}

local function send_to_right_tmux_pane(message, success_notify)
  local tmp_file = os.tmpname()
  local f = io.open(tmp_file, "w")
  if f then
    f:write(message)
    f:close()
  end

  local current_pane = vim.fn.system("tmux display-message -p '#{pane_id}'"):gsub("%s+", "")
  local target_pane = vim.fn
    .system(
      string.format(
        "tmux select-pane -R -t %s \\; display-message -p '#{pane_id}' \\; select-pane -t %s",
        current_pane,
        current_pane
      )
    )
    :gsub("%s+", "")

  if target_pane == "" or target_pane == current_pane then
    vim.notify("No pane to the right found", vim.log.levels.WARN)
    os.remove(tmp_file)
    return
  end

  vim.fn.system(string.format("tmux load-buffer %s", tmp_file))
  vim.fn.system(string.format("tmux paste-buffer -t %s", target_pane))

  os.remove(tmp_file)
  if success_notify then
    vim.notify(success_notify, vim.log.levels.INFO)
  end
end

local function get_buf_git_root_and_relpath(bufnr)
  local abs_path = vim.api.nvim_buf_get_name(bufnr)
  if abs_path == "" then
    return nil, nil, "Current buffer has no file path"
  end

  local git_root = fs_util.get_git_root()
  if not git_root then
    return nil, nil, "Not in a git repository"
  end

  abs_path = vim.fn.fnamemodify(abs_path, ":p")
  git_root = vim.fn.fnamemodify(git_root, ":p")
  if git_root:sub(-1) == "/" then
    git_root = git_root:sub(1, -2)
  end

  if abs_path:sub(1, #git_root) ~= git_root then
    return nil, nil, "File is not under git root"
  end

  local relpath = abs_path:sub(#git_root + 1)
  if relpath:sub(1, 1) == "/" then
    relpath = relpath:sub(2)
  end

  return git_root, relpath, nil
end

local function git_diff_lines_for_file(git_root, relpath, opts)
  opts = opts or {}
  local unified = opts.unified
  local inter_hunk_context = opts.inter_hunk_context

  local cmd = { "git", "-C", git_root, "diff", "--no-color" }
  if type(unified) == "number" then
    table.insert(cmd, "-U" .. tostring(unified))
  end
  if type(inter_hunk_context) == "number" then
    table.insert(cmd, "--inter-hunk-context=" .. tostring(inter_hunk_context))
  end
  table.insert(cmd, "--")
  table.insert(cmd, relpath)

  local out = vim.fn.systemlist(cmd)
  if vim.v.shell_error ~= 0 then
    return nil, "git diff failed"
  end

  if #out > 0 then
    return out, nil
  end

  local untracked = vim.fn.systemlist({ "git", "-C", git_root, "ls-files", "--others", "--exclude-standard", "--", relpath })
  if vim.v.shell_error ~= 0 then
    return nil, "git ls-files failed"
  end
  if #untracked == 0 then
    return {}, nil
  end

  cmd = { "git", "-C", git_root, "diff", "--no-color", "--no-index" }
  if type(unified) == "number" then
    table.insert(cmd, "-U" .. tostring(unified))
  end
  if type(inter_hunk_context) == "number" then
    table.insert(cmd, "--inter-hunk-context=" .. tostring(inter_hunk_context))
  end
  table.insert(cmd, "--")
  table.insert(cmd, "/dev/null")
  table.insert(cmd, relpath)

  out = vim.fn.systemlist(cmd)
  local exit_code = vim.v.shell_error
  if exit_code ~= 0 and exit_code ~= 1 then
    return nil, "git diff --no-index failed"
  end

  return out, nil
end

local function git_diff_lines_for_buffer(git_root, relpath, bufnr, opts)
  opts = opts or {}
  local unified = opts.unified
  local inter_hunk_context = opts.inter_hunk_context

  if not vim.bo[bufnr].modified then
    return git_diff_lines_for_file(git_root, relpath, { unified = unified, inter_hunk_context = inter_hunk_context })
  end

  local tmp_new = os.tmpname()
  local tmp_old = os.tmpname()

  local ok_new, err_new = fs_util.safe_file_write(tmp_new, table.concat(vim.api.nvim_buf_get_lines(bufnr, 0, -1, false), "\n") .. "\n")
  if not ok_new then
    os.remove(tmp_new)
    os.remove(tmp_old)
    return nil, err_new or "Failed to write temp file"
  end

  local is_tracked = vim.fn.system({ "git", "-C", git_root, "ls-files", "--error-unmatch", "--", relpath })
  local tracked_ok = vim.v.shell_error == 0 and is_tracked ~= ""

  local old_path = "/dev/null"
  if tracked_ok then
    local index_blob = vim.fn.system({ "git", "-C", git_root, "show", ":" .. relpath })
    if vim.v.shell_error == 0 then
      fs_util.safe_file_write(tmp_old, index_blob)
      old_path = tmp_old
    else
      local head_blob = vim.fn.system({ "git", "-C", git_root, "show", "HEAD:" .. relpath })
      if vim.v.shell_error == 0 then
        fs_util.safe_file_write(tmp_old, head_blob)
        old_path = tmp_old
      end
    end
  end

  local cmd = { "git", "-C", git_root, "diff", "--no-color", "--no-index" }
  if type(unified) == "number" then
    table.insert(cmd, "-U" .. tostring(unified))
  end
  if type(inter_hunk_context) == "number" then
    table.insert(cmd, "--inter-hunk-context=" .. tostring(inter_hunk_context))
  end
  table.insert(cmd, "--")
  table.insert(cmd, old_path)
  table.insert(cmd, tmp_new)

  local out = vim.fn.systemlist(cmd)
  local exit_code = vim.v.shell_error

  os.remove(tmp_new)
  os.remove(tmp_old)

  if exit_code ~= 0 and exit_code ~= 1 then
    return nil, "git diff --no-index failed"
  end

  return out, nil
end

local function parse_hunk_new_range(hunk_header)
  local start_s, count_s = hunk_header:match("^@@%s+%-%d+,?%d*%s+%+(%d+),?(%d*)%s+@@")
  if not start_s then
    return nil, nil
  end

  local start_n = tonumber(start_s)
  local count_n
  if count_s == "" then
    count_n = 1
  else
    count_n = tonumber(count_s)
  end

  return start_n, count_n
end

local function extract_patch_for_line_range(diff_lines, start_lnum, end_lnum, opts)
  opts = opts or {}
  local single_hunk = opts.single_hunk == true

  local first_hunk_idx
  for i, line in ipairs(diff_lines) do
    if line:match("^@@") then
      first_hunk_idx = i
      break
    end
  end
  if not first_hunk_idx then
    return nil
  end

  local header_lines = {}
  for i = 1, first_hunk_idx - 1 do
    table.insert(header_lines, diff_lines[i])
  end

  local hunks = {}
  local current_hunk
  for i = first_hunk_idx, #diff_lines do
    local line = diff_lines[i]
    if line:match("^@@") then
      local new_start, new_count = parse_hunk_new_range(line)
      current_hunk = { new_start = new_start, new_count = new_count, lines = { line } }
      table.insert(hunks, current_hunk)
    elseif current_hunk then
      table.insert(current_hunk.lines, line)
    end
  end

  local function intersects(hunk)
    if not hunk.new_start or hunk.new_count == nil then
      return false
    end

    if hunk.new_count == 0 then
      return start_lnum <= hunk.new_start and hunk.new_start <= end_lnum
    end

    local new_end = hunk.new_start + hunk.new_count - 1
    return not (end_lnum < hunk.new_start or start_lnum > new_end)
  end

  local selected = {}
  for _, hunk in ipairs(hunks) do
    if intersects(hunk) then
      if single_hunk then
        selected = { hunk }
        break
      end
      table.insert(selected, hunk)
    end
  end
  if #selected == 0 then
    return nil
  end

  local out = {}
  for _, l in ipairs(header_lines) do
    table.insert(out, l)
  end
  for _, hunk in ipairs(selected) do
    for _, l in ipairs(hunk.lines) do
      table.insert(out, l)
    end
  end

  return table.concat(out, "\n")
end

function M.send_diagnostics()
  local file_path = vim.api.nvim_buf_get_name(0)
  local diagnostics = vim.diagnostic.get(0)

  if #diagnostics == 0 then
    vim.notify("No diagnostics found", vim.log.levels.INFO)
    return
  end

  local diag_lines = {}
  for _, d in ipairs(diagnostics) do
    local severity = vim.diagnostic.severity[d.severity] or "UNKNOWN"
    table.insert(diag_lines, string.format("Line %d: [%s] %s", d.lnum + 1, severity, d.message))
  end

  local message =
    string.format("Here are the diagnostics for file `%s`:\n\n```\n%s\n```", file_path, table.concat(diag_lines, "\n"))

  send_to_right_tmux_pane(message, "Diagnostics sent to right pane")
end

function M.send_current_line()
  local file_path = vim.api.nvim_buf_get_name(0)
  local line_num = vim.api.nvim_win_get_cursor(0)[1]
  local line_content = vim.api.nvim_get_current_line()

  local message = string.format("File: `%s`:%d\n\n```\n%s\n```", file_path, line_num, line_content)

  send_to_right_tmux_pane(message, "Current line sent to right pane")
end

function M.send_selection()
  local file_path = vim.api.nvim_buf_get_name(0)
  vim.cmd('noau normal! "vy')
  local selection = vim.fn.getreg("v")
  local line_num = vim.fn.getpos("'<")[2]

  local message = string.format("File: `%s`:%d\n\n```\n%s\n```", file_path, line_num, selection)

  send_to_right_tmux_pane(message, "Selection sent to right pane")
end

function M.send_git_hunk()
  local git_root, relpath, err = get_buf_git_root_and_relpath(0)
  if not git_root then
    vim.notify(err, vim.log.levels.WARN)
    return
  end

  local start_lnum, end_lnum
  if fs_util.in_visual() then
    start_lnum = vim.fn.getpos("'<")[2]
    end_lnum = vim.fn.getpos("'>")[2]
    if start_lnum > end_lnum then
      start_lnum, end_lnum = end_lnum, start_lnum
    end
  else
    start_lnum = vim.api.nvim_win_get_cursor(0)[1]
    end_lnum = start_lnum
  end

  local diff_lines, diff_err = git_diff_lines_for_buffer(git_root, relpath, 0, { unified = 0, inter_hunk_context = 0 })
  if not diff_lines then
    vim.notify(diff_err, vim.log.levels.ERROR)
    return
  end
  if #diff_lines == 0 then
    vim.notify("No git diff found for current file", vim.log.levels.INFO)
    return
  end

  local patch = extract_patch_for_line_range(diff_lines, start_lnum, end_lnum, { single_hunk = start_lnum == end_lnum })
  if not patch then
    vim.notify("No git hunk found for selected line(s)", vim.log.levels.INFO)
    return
  end

  local range_label = start_lnum == end_lnum and ("line " .. start_lnum) or ("lines " .. start_lnum .. "-" .. end_lnum)
  local message = string.format("Git hunk(s) for `%s` (%s):\n\n```diff\n%s\n```", relpath, range_label, patch)

  send_to_right_tmux_pane(message, "Git hunk sent to right pane")
end

function M.send_git_diff_file()
  local git_root, relpath, err = get_buf_git_root_and_relpath(0)
  if not git_root then
    vim.notify(err, vim.log.levels.WARN)
    return
  end

  local diff_lines, diff_err = git_diff_lines_for_buffer(git_root, relpath, 0)
  if not diff_lines then
    vim.notify(diff_err, vim.log.levels.ERROR)
    return
  end
  if #diff_lines == 0 then
    vim.notify("No git diff found for current file", vim.log.levels.INFO)
    return
  end

  local message = string.format("Git diff for `%s`:\n\n```diff\n%s\n```", relpath, table.concat(diff_lines, "\n"))

  send_to_right_tmux_pane(message, "Git diff sent to right pane")
end

return M
