local M = {}

M.confirm = function(message, callback)
  local opts = {
    prompt = message .. " y/n: ",
  }
  vim.ui.input(opts, function(value)
    callback(value == "y" or value == "Y")
  end)
end

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

--- Determine if a path is absolute (supports POSIX and Windows forms)
---@param path string|nil
---@return boolean
function M.is_absolute_path(path)
  return type(path) == "string" and (path:match("^/") ~= nil or path:match("^%a:[/\\]") ~= nil)
end

---@param path string|nil
---@param base_dir string|nil
---@return string|nil
function M.normalize_path(path, base_dir)
  if type(path) ~= "string" or path == "" then
    return nil
  end

  if base_dir and base_dir ~= "" and not M.is_absolute_path(path) then
    path = base_dir .. "/" .. path
  end

  return vim.fn.fnamemodify(path, ":p")
end

---@param file_path string
---@return boolean
function M.file_exists(file_path)
  local stat = vim.uv.fs_stat(file_path)
  return stat and stat.type == "file" or false
end

---@param path string File path
---@return string|nil content File content or nil
---@return string|nil error Error message if failed
function M.safe_file_read(path)
  local file = io.open(path, "r")
  if not file then
    return nil, "Could not open file for reading: " .. path
  end
  local content = file:read("*a")
  file:close()
  return content, nil
end

---@param path string File path
---@param content string Content to write
---@param mode string|nil File mode (default: "w")
---@return boolean success True if successful
---@return string|nil error Error message if failed
function M.safe_file_write(path, content, mode)
  mode = mode or "w"
  local file = io.open(path, mode)
  if not file then
    return false, "Could not open file for writing: " .. path
  end
  file:write(content)
  file:close()
  return true, nil
end

---@param prompt string|table Prompt string or options table
---@param callback fun(input: string|nil) Callback function
function M.safe_input(prompt, callback)
  local opts = type(prompt) == "string" and { prompt = prompt } or prompt
  local ok, result = pcall(vim.fn.input, opts)
  if ok and result and result ~= "" then
    callback(result)
  end
end

---@return string
function M.get_plugin_src_dir()
  return vim.fn.stdpath("config") .. "/lua/plugins_local_src"
end

---@param glob string
---@return string
function M.glob_to_lua_pattern(glob)
  local escaped_glob = vim.pesc(glob)

  local partial_pattern = escaped_glob:gsub("%%%[!", "NEGATE_CLASS")

  partial_pattern = partial_pattern:gsub(vim.pesc("%*%*/%*"), "TRIPLE_ASTERISK")
  partial_pattern = partial_pattern:gsub(vim.pesc("%*%*/"), "DOUBLE_ASTERISK_SLASH")
  partial_pattern = partial_pattern:gsub(vim.pesc("%*%*"), "DOUBLE_ASTERISK")
  partial_pattern = partial_pattern:gsub(vim.pesc("%*"), "SINGLE_ASTERISK")
  partial_pattern = partial_pattern:gsub(vim.pesc("%?"), "QUESTION_MARK")

  partial_pattern = partial_pattern:gsub("TRIPLE_ASTERISK", ".*") -- *** matches anything
  partial_pattern = partial_pattern:gsub("DOUBLE_ASTERISK_SLASH", ".*/") -- **/ matches zero or more chars including /
  partial_pattern = partial_pattern:gsub("DOUBLE_ASTERISK", ".*") -- ** matches anything
  partial_pattern = partial_pattern:gsub("SINGLE_ASTERISK", "[^/]*") -- * matches anything except /
  partial_pattern = partial_pattern:gsub("QUESTION_MARK", "[^/]") -- ? matches single char except /

  local pattern = partial_pattern:gsub("NEGATE_CLASS", "[^") -- [! becomes [^

  return pattern
end

---@return string|nil
function M.get_git_root()
  return vim.fs.root(0, ".git")
end

---@return string|nil
function M.get_project_root()
  return vim.fs.root(0, ".git") or vim.env.PWD
end

---@param str string
---@return string
function M.escape_shell_arg(str)
  return "'" .. str:gsub("'", [['\'']]) .. "'"
end

return M
