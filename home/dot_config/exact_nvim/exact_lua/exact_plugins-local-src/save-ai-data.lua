local M = {}

local TEST_PATTERNS = {
  "**/*.test.*",
  "**/*.spec.*",
  "**/*test*",
  "**/*spec*",
  "**/*.e2e.*",
  "**/*.integration.*",
  "**/*.unit.*",
  "**/*.mock.*",
  "**/__mocks__/**/*",
  "**/__tests__/**/*",
  "**/mocks/**/*",
  "**/tests/**/*",
  "**/specs/**/*",
  "**/test/**/*",
  "**/mock/**/*",
  "**/fixtures/**/*",
}

local ALWAYS_EXCLUDE = {
  "**/*.log",
  "**/*.tmp",
  "**/*.swp",
  "**/*.bak",
  "**/*.snap",
}

-- File patterns for different categories
local PATTERNS = {
  source = {
    include = {
      "**/*.lua",
      "**/*.js",
      "**/*.ts",
      "**/*.jsx",
      "**/*.tsx",
      "**/*.py",
      "**/*.go",
      "**/*.rs",
      "**/*.java",
      "**/*.c",
      "**/*.cpp",
      "**/*.h",
      "**/*.hpp",
    },
    exclude = TEST_PATTERNS,
  },
  test = {
    include = TEST_PATTERNS,
    exclude = ALWAYS_EXCLUDE,
  },
  config = {
    include = { "*.json", "*.yaml", "*.yml", "*.toml", "*.ini", "*.conf", "*.config.*" },
    exclude = ALWAYS_EXCLUDE,
  },
}

-- Convert glob pattern to Lua pattern
local function glob_to_lua_pattern(glob)
  -- Escape special Lua pattern characters except * and ?
  local pattern = glob:gsub("[%(%)%.%+%-%^%$%[%]%%]", "%%%1")

  -- Handle ** (match any directories)
  pattern = pattern:gsub("%*%*", ".-")

  -- Handle * (match anything except /)
  pattern = pattern:gsub("%*", "[^/]*")

  -- Handle ? (match single character except /)
  pattern = pattern:gsub("%?", "[^/]")

  -- Anchor the pattern
  return "^" .. pattern .. "$"
end

local function matches_any_pattern(file_path, patterns)
  for _, pattern in ipairs(patterns) do
    local lua_pattern = glob_to_lua_pattern(pattern)
    if file_path:match(lua_pattern) then
      return true
    end
  end
  return false
end

local function get_relative_path(file_path)
  local cwd = vim.uv.cwd()
  if file_path:sub(1, #cwd) == cwd then
    return file_path:sub(#cwd + 2) -- +2 to skip the trailing slash
  end
  return file_path
end

-- Helper function for safe file writing with error handling
local function safe_write_to_file(output_path, content, mode)
  local file = io.open(output_path, mode)
  if file then
    file:write(content)
    file:close()
    return true
  end
  return false
end

local function file_exists_in_output(output_path, relative_file_name)
  if vim.uv.fs_stat(output_path) then
    local file = io.open(output_path, "r")
    if file then
      local content = file:read("*a")
      file:close()
      if content then
        local file_pattern = "#FILE: " .. vim.pesc(relative_file_name)
        return content:match(file_pattern) ~= nil
      end
    end
  end
  return false
end

-- Helper function to handle duplicate checking and writing
local function write_content_if_needed(output_path, content, relative_path, append, first_write)
  if not content then
    return false, first_write
  end

  -- Only check for duplicates if appending
  if append and file_exists_in_output(output_path, relative_path) then
    vim.notify("File already exists in output. Skipping: " .. relative_path, vim.log.levels.WARN)
    return false, first_write
  end

  -- For replace mode, first file overwrites, subsequent files append
  -- For append mode, all files append
  local write_mode = (append or not first_write) and "a" or "w"

  if safe_write_to_file(output_path, content, write_mode) then
    return true, false -- success, first_write becomes false
  else
    vim.notify("Error: Could not write to file " .. output_path, vim.log.levels.ERROR)
    return false, first_write
  end
end

local function discover_files(path, filter_type, custom_pattern)
  local files = {}

  local result = vim
    .system({ "git", "ls-files", "--full-name" }, {
      cwd = path,
      text = true,
    })
    :wait()
  if result.code == 0 then
    for line in result.stdout:gmatch("[^\r\n]+") do
      table.insert(files, vim.fs.joinpath(path, line))
    end
  end

  if filter_type == "all" then
    return files
  elseif filter_type == "custom" then
    -- Custom pattern filtering (treat as Lua pattern)
    if not custom_pattern or custom_pattern == "" then
      vim.notify("No custom pattern provided", vim.log.levels.WARN)
      return {}
    end

    local filtered_files = {}
    for _, file in ipairs(files) do
      local relative_file = get_relative_path(file)
      local success, match = pcall(string.match, relative_file, custom_pattern)
      if success and match then
        table.insert(filtered_files, file)
      end
    end

    return filtered_files
  else
    local pattern = PATTERNS[filter_type]
    if not pattern then
      vim.notify("Invalid filter type: " .. filter_type, vim.log.levels.ERROR)
      return {}
    end

    local include_patterns = pattern.include
    local exclude_patterns = pattern.exclude or {}

    local filtered_files = {}
    for _, file in ipairs(files) do
      local relative_file = get_relative_path(file)

      local include = matches_any_pattern(relative_file, include_patterns)

      if include then
        local exclude = matches_any_pattern(relative_file, exclude_patterns)

        if not exclude then
          table.insert(filtered_files, file)
        end
      end
    end

    return filtered_files
  end
end

local function format_file_content(file_path)
  local relative_path = get_relative_path(file_path)
  local file = io.open(file_path, "r")

  if not file then
    return nil
  end

  local content = file:read("*a")
  file:close()

  if not content then
    return nil
  end

  return string.format(
    "\n---------------------------------------------\n"
      .. "#FILE: %s"
      .. "\n---------------------------------------------\n"
      .. "%s"
      .. "\n---------------------------------------------\n"
      .. "\n",
    relative_path,
    content
  )
end

function M.save_buffer_to_ai_file(append)
  local output_path = vim.fs.normalize("~/ai_data.txt")
  local relative_file_name = get_relative_path(vim.api.nvim_buf_get_name(0))
  local file_content = vim.api.nvim_buf_get_lines(0, 0, -1, false)

  local content = string.format(
    "\n---------------------------------------------\n"
      .. "#FILE: %s"
      .. "\n---------------------------------------------\n"
      .. "%s"
      .. "\n---------------------------------------------\n"
      .. "\n",
    relative_file_name,
    table.concat(file_content, "\n")
  )

  if append and file_exists_in_output(output_path, relative_file_name) then
    vim.notify("File already exists in " .. output_path .. ". Skipping to prevent duplicate.", vim.log.levels.WARN)
    return
  end

  local mode = append and "a" or "w"
  if safe_write_to_file(output_path, content, mode) then
    vim.notify(
      "Buffer content saved to " .. output_path .. " (" .. (append and "append" or "replace") .. ")",
      vim.log.levels.INFO
    )
  else
    vim.notify("Error: Could not open file " .. output_path, vim.log.levels.ERROR)
  end
end

-- Enhanced function for files/folders with filtering (append/replace controlled by keymap)
function M.save_path_to_ai_file(path, append)
  -- check if no .git directory exists exit
  if not vim.fs.find(".git", { path = path, upward = true })[1] then
    vim.notify("Not in a git repository", vim.log.levels.ERROR)
    return
  end

  local output_path = vim.fs.normalize("~/ai_data.txt")

  -- Check if path exists
  local stat = vim.uv.fs_stat(path)
  if not stat then
    vim.notify("Path does not exist: " .. path, vim.log.levels.ERROR)
    return
  end

  -- If it's a single file, save it directly
  if stat.type == "file" then
    local relative_path = get_relative_path(path)
    local content = format_file_content(path)
    local success, _ = write_content_if_needed(output_path, content, relative_path, append, true)

    if success then
      vim.notify(
        "File saved: " .. relative_path .. " (" .. (append and "append" or "replace") .. ")",
        vim.log.levels.INFO
      )
    end
    return
  end

  -- For directories, show ONLY filter selection UI (no mode selection)
  local filter_options = {
    "All tracked files",
    "Source files only",
    "Test files only",
    "Config files only",
    "Custom pattern",
  }

  vim.ui.select(filter_options, {
    prompt = "Select files to save:",
    format_item = function(item)
      return item
    end,
  }, function(choice)
    if not choice then
      return
    end

    local filter_type = choice:match("^(%w+)")

    if filter_type == "Custom" then
      vim.ui.input({
        prompt = "Enter Lua pattern: ",
        default = "",
      }, function(pattern)
        if pattern and pattern ~= "" then
          M.process_files(path, "custom", pattern, append)
        end
      end)
    else
      local type_map = {
        All = "all",
        Source = "source",
        Test = "test",
        Config = "config",
      }
      M.process_files(path, type_map[filter_type], nil, append)
    end
  end)
end

-- Process discovered files with explicit append/replace mode
function M.process_files(path, filter_type, custom_pattern, append)
  local output_path = vim.fs.normalize("~/ai_data.txt")
  local files = discover_files(path, filter_type, custom_pattern)

  if #files == 0 then
    vim.notify("No files found matching criteria", vim.log.levels.WARN)
    return
  end

  local saved_count = 0
  local skipped_count = 0
  local first_write = true

  for _, file_path in ipairs(files) do
    local relative_path = get_relative_path(file_path)
    local content = format_file_content(file_path)
    local success, new_first_write = write_content_if_needed(output_path, content, relative_path, append, first_write)

    if success then
      saved_count = saved_count + 1
      first_write = new_first_write
    else
      skipped_count = skipped_count + 1
    end
  end

  vim.notify(
    string.format(
      "Processed %d files: %d saved, %d skipped%s (%s mode)",
      #files,
      saved_count,
      skipped_count,
      append and " (duplicates)" or "",
      append and "append" or "replace"
    ),
    vim.log.levels.INFO
  )
end

return M
