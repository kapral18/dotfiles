local common_utils = require("utils.common")

local M = {}

local DELIMITER = "----------------------------------------------"

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

local function matches_any_pattern(file_path, patterns)
  for _, pattern in ipairs(patterns) do
    local lua_pattern = "^" .. common_utils.glob_to_lua_pattern(pattern) .. "$"
    if file_path:match(lua_pattern) then
      return true
    end
  end
  return false
end

local function get_relative_path(file_path, git_root)
  if vim.startswith(file_path, git_root) then
    return file_path:sub(#git_root + 2)
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

local function file_exists_in_output_with_content(output_path, relative_file_name)
  if vim.uv.fs_stat(output_path) then
    local file = io.open(output_path, "r")
    if file then
      local content = file:read("*a")
      file:close()
      if content then
        local escaped_delimiter = vim.pesc(DELIMITER)
        local file_pattern = "#FILE: "
          .. vim.pesc(relative_file_name)
          .. "\n"
          .. escaped_delimiter
          .. "\n(.-)\n"
          .. escaped_delimiter
        local existing_content = content:match(file_pattern)
        if existing_content then
          return true, existing_content
        end
      end
    end
  end
  return false, nil
end

-- Legacy function for backward compatibility
local function file_exists_in_output(output_path, relative_file_name)
  local exists, _ = file_exists_in_output_with_content(output_path, relative_file_name)
  return exists
end

-- Replace existing file content in ai_data.txt
local function replace_file_content_in_output(output_path, relative_file_name, new_content)
  local file = io.open(output_path, "r")
  if not file then
    return false
  end

  local full_content = file:read("*a")
  file:close()

  local escaped_delimiter = vim.pesc(DELIMITER)
  local section_pattern = "(#FILE: "
    .. vim.pesc(relative_file_name)
    .. "\n"
    .. escaped_delimiter
    .. "\n).-(\n"
    .. escaped_delimiter
    .. ")"
  local new_section = "#FILE: " .. relative_file_name .. "\n" .. DELIMITER .. "\n" .. new_content .. "\n" .. DELIMITER

  local updated_content = full_content:gsub(section_pattern, new_section, 1)

  -- Write back the updated content
  local write_file = io.open(output_path, "w")
  if write_file then
    write_file:write(updated_content)
    write_file:close()
    return true
  end
  return false
end

-- Enhanced function to handle duplicate checking with content comparison
local function write_content_with_smart_replace(
  output_path,
  content,
  relative_path,
  append,
  first_write,
  file_content_only
)
  if not content then
    return false, first_write
  end

  local exists, existing_content = file_exists_in_output_with_content(output_path, relative_path)

  if exists and existing_content then
    -- Compare content (strip whitespace for reliable comparison)
    local existing_trimmed = existing_content:gsub("^%s*(.-)%s*$", "%1")
    local new_trimmed = file_content_only:gsub("^%s*(.-)%s*$", "%1")

    if existing_trimmed == new_trimmed then
      vim.notify("Content unchanged. Skipping: " .. relative_path, vim.log.levels.INFO)
      return false, first_write
    else
      -- Content has changed, replace it
      if replace_file_content_in_output(output_path, relative_path, file_content_only) then
        vim.notify("Content changed. Replaced: " .. relative_path, vim.log.levels.INFO)
        return true, first_write
      else
        vim.notify("Error replacing content for: " .. relative_path, vim.log.levels.ERROR)
        return false, first_write
      end
    end
  else
    -- File doesn't exist, write normally
    local write_mode = (append or not first_write) and "a" or "w"
    if safe_write_to_file(output_path, content, write_mode) then
      return true, false
    else
      vim.notify("Error: Could not write to file " .. output_path, vim.log.levels.ERROR)
      return false, first_write
    end
  end
end

-- Helper function to handle duplicate checking and writing (legacy)
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

function M.remove_entries_by_pattern(pattern_type, custom_pattern)
  local output_path = vim.fs.normalize("~/ai_data.txt")

  if not vim.uv.fs_stat(output_path) then
    vim.notify("ai_data.txt does not exist", vim.log.levels.WARN)
    return
  end

  local file = io.open(output_path, "r")
  if not file then
    vim.notify("Could not read ai_data.txt", vim.log.levels.ERROR)
    return
  end

  local content = file:read("*a")
  file:close()

  local removed_count = 0
  local sections = {}

  local escaped_delimiter = vim.pesc(DELIMITER)
  local section_pattern = "(#FILE: [^\n]+\n" .. escaped_delimiter .. "\n.-\n" .. escaped_delimiter .. ")"

  for section in content:gmatch(section_pattern) do
    local file_name = section:match("#FILE: ([^\n]+)")
    local should_remove = false

    if pattern_type == "custom" and custom_pattern then
      should_remove = file_name:match(custom_pattern) ~= nil
    elseif pattern_type and PATTERNS[pattern_type] then
      should_remove = matches_any_pattern(file_name, PATTERNS[pattern_type].include or {})
    end

    if should_remove then
      removed_count = removed_count + 1
    else
      table.insert(sections, section)
    end
  end

  -- Write back the filtered content
  local write_file = io.open(output_path, "w")
  if write_file then
    write_file:write(table.concat(sections, "\n"))
    write_file:close()
    vim.notify(string.format("Removed %d entries from ai_data.txt", removed_count), vim.log.levels.INFO)
  else
    vim.notify("Could not write to ai_data.txt", vim.log.levels.ERROR)
  end
end

function M.remove_path_from_ai_data(node_path)
  if not node_path then
    vim.notify("No path provided", vim.log.levels.WARN)
    return
  end

  -- Convert absolute path to relative path from git root
  local git_root = common_utils.get_git_root()
  if not git_root then
    vim.notify("Not in a git repository", vim.log.levels.ERROR)
    return
  end

  local relative_path = get_relative_path(node_path, git_root)

  -- check if the path is a directory
  -- then we need to remove exact match

  if vim.uv.fs_stat(node_path).type == "directory" then
    -- Remove all entries that match the directory pattern
    M.remove_entries_by_pattern("custom", "^" .. vim.pesc(relative_path) .. "/?.*$")
    return
  end

  -- Remove entry by exact relative path pattern
  M.remove_entries_by_pattern("custom", "^" .. vim.pesc(relative_path) .. "$")
end

local function discover_files(path, filter_type, custom_pattern, git_root)
  local files = {}

  local result = vim
    .system({ "git", "ls-files", "--full-name" }, {
      cwd = path,
      text = true,
    })
    :wait()
  if result.code == 0 then
    for line in result.stdout:gmatch("[^\r\n]+") do
      table.insert(files, vim.fs.joinpath(git_root, line))
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
      local relative_file = get_relative_path(file, git_root)
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
      local relative_file = get_relative_path(file, git_root)

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

local function format_file_content(file_path, git_root)
  local relative_path = get_relative_path(file_path, git_root)
  local file = io.open(file_path, "r")

  if not file then
    return nil
  end

  local content = file:read("*a")
  file:close()

  if not content then
    return nil
  end

  return string.format("\n%s\n#FILE: %s\n%s\n%s\n%s\n\n", DELIMITER, relative_path, DELIMITER, content, DELIMITER)
end

-- Enhanced save_buffer_to_ai_file with smart replacement
function M.save_buffer_to_ai_file(append)
  local output_path = vim.fs.normalize("~/ai_data.txt")
  local git_root = common_utils.get_git_root()
  if not git_root then
    vim.notify("Not in a git repository", vim.log.levels.ERROR)
    return
  end

  local relative_file_name = get_relative_path(vim.api.nvim_buf_get_name(0), git_root)
  local file_content = table.concat(vim.api.nvim_buf_get_lines(0, 0, -1, false), "\n")

  local formatted_content =
    string.format("\n%s\n#FILE: %s\n%s\n%s\n%s\n\n", DELIMITER, relative_file_name, DELIMITER, file_content, DELIMITER)

  local success, _ =
    write_content_with_smart_replace(output_path, formatted_content, relative_file_name, append, true, file_content)

  if success then
    vim.notify("Buffer content processed for " .. output_path, vim.log.levels.INFO)
  end
end

-- Remove current buffer from ai_data.txt
function M.remove_current_buffer_from_ai_file()
  local git_root = common_utils.get_git_root()
  if not git_root then
    vim.notify("Not in a git repository", vim.log.levels.ERROR)
    return
  end

  local relative_file_name = get_relative_path(vim.api.nvim_buf_get_name(0), git_root)

  -- Remove entry by exact relative path pattern
  M.remove_entries_by_pattern("custom", "^" .. vim.pesc(relative_file_name) .. "$")
end

-- Enhanced function for files/folders with filtering (append/replace controlled by keymap)
function M.save_path_to_ai_file(path, append)
  local git_root = common_utils.get_git_root()

  if not git_root then
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

  -- If it's a single file, save it directly with smart replacement
  if stat.type == "file" then
    local relative_path = get_relative_path(path, git_root)
    local file = io.open(path, "r")
    if not file then
      vim.notify("Could not read file: " .. path, vim.log.levels.ERROR)
      return
    end

    local file_content = file:read("*a")
    file:close()

    local formatted_content = format_file_content(path, git_root)
    local success, _ =
      write_content_with_smart_replace(output_path, formatted_content, relative_path, append, true, file_content)

    if success then
      vim.notify(
        "File processed: " .. relative_path .. " (" .. (append and "append" or "replace") .. ")",
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
          M.process_files(path, "custom", pattern, append, git_root)
        end
      end)
    else
      local type_map = {
        All = "all",
        Source = "source",
        Test = "test",
        Config = "config",
      }
      M.process_files(path, type_map[filter_type], nil, append, git_root)
    end
  end)
end

function M.process_files(path, filter_type, custom_pattern, append, git_root)
  local output_path = vim.fs.normalize("~/ai_data.txt")
  local files = discover_files(path, filter_type, custom_pattern, git_root)

  if #files == 0 then
    vim.notify("No files found matching criteria", vim.log.levels.WARN)
    return
  end

  local saved_count = 0
  local skipped_count = 0
  local replaced_count = 0
  local first_write = true

  for _, file_path in ipairs(files) do
    local relative_path = get_relative_path(file_path, git_root)
    local file = io.open(file_path, "r")
    if file then
      local file_content = file:read("*a")
      file:close()

      local formatted_content = format_file_content(file_path, git_root)

      -- Check if file exists and content changed
      local exists, existing_content = file_exists_in_output_with_content(output_path, relative_path)

      if exists and existing_content then
        local existing_trimmed = existing_content:gsub("^%s*(.-)%s*$", "%1")
        local new_trimmed = file_content:gsub("^%s*(.-)%s*$", "%1")

        if existing_trimmed == new_trimmed then
          skipped_count = skipped_count + 1
        else
          -- Content changed, replace it
          if replace_file_content_in_output(output_path, relative_path, file_content) then
            replaced_count = replaced_count + 1
          end
        end
      else
        -- New file, write normally
        local success, new_first_write =
          write_content_if_needed(output_path, formatted_content, relative_path, append, first_write)
        if success then
          saved_count = saved_count + 1
          first_write = new_first_write
        end
      end
    end
  end

  vim.notify(
    string.format(
      "Processed %d files: %d new, %d replaced, %d skipped (%s mode)",
      #files,
      saved_count,
      replaced_count,
      skipped_count,
      append and "append" or "replace"
    ),
    vim.log.levels.INFO
  )
end

return M
