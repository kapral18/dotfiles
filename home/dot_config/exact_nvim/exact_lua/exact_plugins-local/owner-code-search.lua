-- CODEOWNERS Search Module for Neovim
-- Provides functionality to search code within directories owned by specific teams/users
-- based on GitHub CODEOWNERS file patterns

local M = {}

-- Configuration
M.config = {
  codeowners_paths = {
    "CODEOWNERS",
    ".github/CODEOWNERS",
    ".gitlab/CODEOWNERS",
    ".bitbucket/CODEOWNERS",
    "docs/CODEOWNERS",
  },
  cache_ttl = 60 * 60 * 24, -- 24 hours
  show_search_progress = true,
  fd_extra_args = { "--hidden" },
  rg_extra_args = { "--hidden" },
}

-- Cache for parsed CODEOWNERS data
local cache = {
  data = nil,
  timestamp = 0,
  file_path = nil,
}

-- Helper function to locate CODEOWNERS file
local function find_codeowners_file()
  for _, path in ipairs(M.config.codeowners_paths) do
    local files = vim.fs.find(path, { upward = true, limit = 1 })
    if #files > 0 then
      return files[1]
    end
  end
  return nil
end

-- Helper function to check if cache is valid
local function is_cache_valid(file_path)
  if not cache.data or cache.file_path ~= file_path then
    return false
  end

  local current_time = os.time()
  return (current_time - cache.timestamp) < M.config.cache_ttl
end

-- Helper function to split line into pattern and owners section
local function split_line_parts(input)
  local result = { pattern = "", owners_text = "" }
  local in_pattern = true
  local skip_next = false
  local pattern_chars = {}

  -- Process character by character
  for i = 1, #input do
    local char = input:sub(i, i)

    if skip_next then
      -- Add escaped character to pattern
      table.insert(pattern_chars, char)
      skip_next = false
    elseif char == "\\" and in_pattern then
      -- Mark next character as escaped
      table.insert(pattern_chars, char) -- Keep the backslash for proper pattern matching
      skip_next = true
    elseif char == " " and in_pattern then
      -- First unescaped space marks end of pattern
      in_pattern = false
      result.pattern = table.concat(pattern_chars)
      result.owners_text = input:sub(i + 1) -- Skip the space
      break
    else
      if in_pattern then
        table.insert(pattern_chars, char)
      end
    end
  end

  -- If we never found a space, the entire line is the pattern
  if in_pattern then
    result.pattern = table.concat(pattern_chars)
    result.owners_text = ""
  end

  return result
end

-- Helper function to extract owners from owners text section
local function extract_owners(owners_text)
  local owners_list = {}
  -- Remove leading/trailing whitespace and split by whitespace
  owners_text = owners_text:match("^%s*(.-)%s*$") or ""

  for owner in owners_text:gmatch("%S+") do
    -- Skip inline comments
    if not owner:match("^#") then
      table.insert(owners_list, owner)
    end
  end

  return owners_list
end

-- Helper function to convert CODEOWNERS pattern to filesystem path
local function pattern_to_path(pattern)
  -- Remove leading slash if present
  pattern = pattern:gsub("^/", "")

  -- Remove trailing wildcards for directory matching
  pattern = pattern:gsub("%*+$", "")
  pattern = pattern:gsub("/$", "")

  -- Unescape spaces and other characters
  pattern = pattern:gsub("\\(.)", "%1")

  return pattern
end

-- Parse a single CODEOWNERS line
function M.parse_codeowners_line(line)
  -- Remove leading/trailing whitespace
  line = line:match("^%s*(.-)%s*$") or ""

  -- Skip comments and empty lines
  if line == "" or line:match("^#") then
    return nil
  end

  -- Process the line
  local parts = split_line_parts(line)
  if parts.pattern == "" then
    return nil
  end

  local file_pattern = parts.pattern
  local owners = extract_owners(parts.owners_text)

  -- Skip lines with no owners
  if #owners == 0 then
    return nil
  end

  return file_pattern, owners
end

-- Load and parse CODEOWNERS file with caching
local function load_codeowners_data()
  local file_path = find_codeowners_file()
  if not file_path then
    return nil, "No CODEOWNERS file found"
  end

  -- Check cache
  if is_cache_valid(file_path) then
    return cache.data, nil
  end

  -- Read and parse file
  local lines = vim.fn.readfile(file_path)
  if not lines then
    return nil, "Failed to read CODEOWNERS file: " .. file_path
  end

  local data = {}
  for line_num, line in ipairs(lines) do
    local pattern, owners = M.parse_codeowners_line(line)
    if pattern and owners then
      table.insert(data, {
        pattern = pattern,
        path = pattern_to_path(pattern),
        owners = owners,
        line_num = line_num,
      })
    end
  end

  -- Update cache
  cache.data = data
  cache.timestamp = os.time()
  cache.file_path = file_path

  return data, nil
end

-- Find directories matching an owner predicate
local function find_directories_matching_owner(owner_predicate, description)
  local data, err = load_codeowners_data()
  if not data then
    vim.notify(err, vim.log.levels.ERROR)
    return nil
  end

  local directories = {}
  local seen = {}

  for _, entry in ipairs(data) do
    for _, owner in ipairs(entry.owners) do
      if owner_predicate(owner) then
        local path = entry.path
        if not seen[path] then
          seen[path] = true
          table.insert(directories, path)
        end
        break
      end
    end
  end

  if #directories == 0 then
    vim.notify("No directories found for: " .. description, vim.log.levels.WARN)
    return nil
  end

  return directories
end

-- Execute search command
local function execute_search(search_config)
  local directories = search_config.directory_finder()
  if not directories then
    return
  end

  local results = {}
  local errors = {}
  local total = #directories
  local processed = 0

  for _, dir in ipairs(directories) do
    if M.config.show_search_progress then
      processed = processed + 1
      print(string.format("Searching %d/%d: %s", processed, total, dir), vim.log.levels.INFO)
    end

    local cmd = vim.list_extend({}, search_config.command)

    -- Add extra arguments from config
    if search_config.extra_args then
      vim.list_extend(cmd, search_config.extra_args)
    end

    table.insert(cmd, search_config.pattern)
    table.insert(cmd, dir)

    local output = vim.fn.systemlist(cmd)
    local exit_code = vim.v.shell_error

    if exit_code == 0 then
      if search_config.process_output then
        search_config.process_output(output, results, dir)
      else
        vim.list_extend(results, output)
      end
    elseif exit_code ~= 1 then -- Exit code 1 usually means no matches
      table.insert(errors, {
        dir = dir,
        code = exit_code,
        output = output,
      })
    end
  end

  -- Handle results
  if #results == 0 then
    local msg = #errors > 0
        and string.format("No %s found (%d directories had errors)", search_config.result_type, #errors)
      or string.format("No %s found in %d directories", search_config.result_type, total)
    print(msg)
    return
  end

  -- Set quickfix list
  vim.fn.setqflist({}, " ", {
    title = search_config.title,
    lines = results,
    efm = search_config.efm,
  })

  print(string.format("Found %d %s in %d directories", #results, search_config.result_type, total))
  vim.cmd("copen")
end

-- Public API Functions

-- Search for code patterns in directories owned by teams (substring match)
function M.owner_code_grep(team, search_pattern)
  if not team or team == "" or not search_pattern or search_pattern == "" then
    vim.notify("Usage: OwnerCodeGrep <team> <search-pattern>", vim.log.levels.ERROR)
    return
  end

  execute_search({
    title = string.format("Grep: '%s' in dirs owned by '%s'", search_pattern, team),
    command = { "rg", "--vimgrep" },
    extra_args = M.config.rg_extra_args,
    pattern = search_pattern,
    result_type = "matches",
    efm = "%f:%l:%c:%m",
    directory_finder = function()
      return find_directories_matching_owner(function(owner)
        return owner:lower():find(team:lower(), 1, true) ~= nil
      end, "team containing '" .. team .. "'")
    end,
  })
end

-- Search for files in directories owned by teams (substring match)
function M.owner_code_fd(team, file_pattern)
  if not team or team == "" or not file_pattern or file_pattern == "" then
    vim.notify("Usage: OwnerCodeFd <team> <file-pattern>", vim.log.levels.ERROR)
    return
  end

  execute_search({
    title = string.format("Files: '%s' in dirs owned by '%s'", file_pattern, team),
    command = { "fd", "--type", "file", "--absolute-path" },
    extra_args = M.config.fd_extra_args,
    pattern = file_pattern,
    result_type = "files",
    efm = "%f",
    directory_finder = function()
      return find_directories_matching_owner(function(owner)
        return owner:lower():find(team:lower(), 1, true) ~= nil
      end, "team containing '" .. team .. "'")
    end,
    process_output = function(output, results)
      for _, line in ipairs(output) do
        local trimmed = line:gsub("%s*$", "")
        if trimmed ~= "" then
          table.insert(results, trimmed)
        end
      end
    end,
  })
end

-- Search for code patterns in directories owned by teams (regex match)
function M.owner_code_grep_pattern(owner_regex, search_pattern)
  if not owner_regex or owner_regex == "" or not search_pattern or search_pattern == "" then
    vim.notify("Usage: OwnerCodeGrepPattern <owner-regex> <search-pattern>", vim.log.levels.ERROR)
    return
  end

  -- Validate regex
  local ok, regex_err = pcall(string.match, "", owner_regex)
  if not ok then
    vim.notify("Invalid regex pattern: " .. regex_err, vim.log.levels.ERROR)
    return
  end

  execute_search({
    title = string.format("Grep: '%s' in dirs matching owner regex '%s'", search_pattern, owner_regex),
    command = { "rg", "--vimgrep" },
    extra_args = M.config.rg_extra_args,
    pattern = search_pattern,
    result_type = "matches",
    efm = "%f:%l:%c:%m",
    directory_finder = function()
      return find_directories_matching_owner(function(owner)
        return owner:match(owner_regex) ~= nil
      end, "owner regex '" .. owner_regex .. "'")
    end,
  })
end

-- Search for files in directories owned by teams (regex match)
function M.owner_code_fd_pattern(owner_regex, file_pattern)
  if not owner_regex or owner_regex == "" or not file_pattern or file_pattern == "" then
    vim.notify("Usage: OwnerCodeFdPattern <owner-regex> <file-pattern>", vim.log.levels.ERROR)
    return
  end

  -- Validate regex
  local ok, regex_err = pcall(string.match, "", owner_regex)
  if not ok then
    vim.notify("Invalid regex pattern: " .. regex_err, vim.log.levels.ERROR)
    return
  end

  execute_search({
    title = string.format("Files: '%s' in dirs matching owner regex '%s'", file_pattern, owner_regex),
    command = { "fd", "--type", "file", "--absolute-path" },
    extra_args = M.config.fd_extra_args,
    pattern = file_pattern,
    result_type = "files",
    efm = "%f",
    directory_finder = function()
      return find_directories_matching_owner(function(owner)
        return owner:match(owner_regex) ~= nil
      end, "owner regex '" .. owner_regex .. "'")
    end,
    process_output = function(output, results)
      for _, line in ipairs(output) do
        local trimmed = line:gsub("%s*$", "")
        if trimmed ~= "" then
          table.insert(results, trimmed)
        end
      end
    end,
  })
end

-- Utility function to list all owners and their directories
function M.list_owners()
  local data, err = load_codeowners_data()
  if not data then
    vim.notify(err, vim.log.levels.ERROR)
    return
  end

  local owner_map = {}
  for _, entry in ipairs(data) do
    for _, owner in ipairs(entry.owners) do
      if not owner_map[owner] then
        owner_map[owner] = {}
      end
      table.insert(owner_map[owner], entry.path)
    end
  end

  local lines = {}
  for owner, paths in pairs(owner_map) do
    table.insert(lines, string.format("%s (%d paths)", owner, #paths))
    for _, path in ipairs(paths) do
      table.insert(lines, "  " .. path)
    end
  end

  vim.fn.setqflist({}, " ", {
    title = "CODEOWNERS Overview",
    lines = lines,
  })
  vim.cmd("copen")
end

-- Clear the cache
function M.clear_cache()
  cache.data = nil
  cache.timestamp = 0
  cache.file_path = nil
  vim.notify("CODEOWNERS cache cleared", vim.log.levels.INFO)
end

-- Setup function for user configuration
function M.setup(opts)
  if opts then
    M.config = vim.tbl_deep_extend("force", M.config, opts)
  end
end

return M
