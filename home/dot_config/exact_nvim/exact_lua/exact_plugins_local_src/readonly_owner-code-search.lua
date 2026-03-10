-- CODEOWNERS Search Module for Neovim
-- Provides functionality to search code within directories owned by specific teams/users
-- based on GitHub CODEOWNERS file patterns

---@class CodeownersConfig
---@field codeowners_paths string[] List of paths to search for CODEOWNERS file
---@field cache_ttl integer Cache time-to-live in seconds
---@field show_search_progress boolean Whether to show search progress
---@field fd_extra_args string[] Extra arguments for fd command
---@field rg_extra_args string[] Extra arguments for rg command

---@class CodeownersEntry
---@field pattern string The original pattern from CODEOWNERS
---@field path string The converted filesystem path
---@field owners string[] List of owners for this pattern
---@field line_num integer Line number in CODEOWNERS file

---@class CodeownersCache
---@field data CodeownersEntry[]|nil Parsed CODEOWNERS data
---@field timestamp integer Unix timestamp of last cache update
---@field file_path string|nil Path to the cached CODEOWNERS file

---@class SearchError
---@field dir string Directory where error occurred
---@field code integer Exit code from command
---@field output string[] Command output

---@class LineParts
---@field pattern string The file pattern part
---@field owners_text string The owners text part

---@class SearchConfig
---@field title string Title for quickfix list
---@field command string[] Base command to execute
---@field extra_args string[]|nil Extra arguments from config
---@field pattern string Search pattern
---@field result_type string Type of results (e.g., "matches", "files")
---@field directory_finder fun(): string[]|nil Function to find directories
---@field process_output fun(output: string[], results: string[], dir: string)|nil Optional output processor

local fs_util = require("util.fs")

local M = {}

local regex_cache = {}
local function validate_and_cache_regex(pattern)
  if regex_cache[pattern] ~= nil then
    return regex_cache[pattern], nil
  end

  local ok, err = pcall(string.match, "", pattern)
  if not ok then
    regex_cache[pattern] = false
    return false, err
  end

  regex_cache[pattern] = true
  return true, nil
end

local function process_file_output(output, results)
  for _, line in ipairs(output) do
    local trimmed = line:gsub("%s*$", "")
    if trimmed ~= "" then
      table.insert(results, trimmed)
    end
  end
end

-- Configuration constants
local CACHE_TTL_24H = 60 * 60 * 24
local DEFAULT_CODEOWNERS_PATHS = {
  "CODEOWNERS",
  ".github/CODEOWNERS",
  ".gitlab/CODEOWNERS",
  ".bitbucket/CODEOWNERS",
  "docs/CODEOWNERS",
}

---@type CodeownersConfig
M.config = {
  codeowners_paths = DEFAULT_CODEOWNERS_PATHS,
  cache_ttl = CACHE_TTL_24H,
  show_search_progress = true,
  fd_extra_args = { "--hidden" },
  rg_extra_args = { "--hidden", "--smart-case" },
}

local function resolve_path(path, base_dir)
  if not path or path == "" then
    return nil
  end

  return fs_util.normalize_path(path, base_dir)
end

local function parse_vimgrep_line(line, base_dir)
  local filename, lnum, col, text = line:match("^(.+):(%d+):(%d+):(.*)$")

  if not filename then
    filename, lnum, text = line:match("^(.+):(%d+):(.*)$")
  end

  if not filename then
    return nil
  end

  local resolved = resolve_path(filename, base_dir)
  if not resolved then
    return nil
  end

  return {
    filename = resolved,
    lnum = tonumber(lnum) or 1,
    col = tonumber(col) or 1,
    text = text and text:gsub("^%s*", "") or line,
  }
end

local function create_qf_item(line, base_dir, result_type)
  local trimmed = line:gsub("%s*$", "")
  if trimmed == "" then
    return nil
  end

  if result_type == "matches" then
    return parse_vimgrep_line(trimmed, base_dir)
  elseif result_type == "files" then
    local resolved = resolve_path(trimmed, base_dir)

    if not resolved then
      return nil
    end

    return { filename = resolved, text = trimmed }
  end

  return { text = trimmed }
end

-- Cache for parsed CODEOWNERS data
---@type CodeownersCache
local cache = {
  data = nil,
  timestamp = 0,
  file_path = nil,
}

-- Helper function to locate CODEOWNERS file
---@return string|nil path Path to CODEOWNERS file or nil if not found
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
---@param file_path string Path to CODEOWNERS file
---@return boolean is_valid Whether cache is still valid
local function is_cache_valid(file_path)
  if not cache.data or cache.file_path ~= file_path then
    return false
  end

  local current_time = os.time()
  return (current_time - cache.timestamp) < M.config.cache_ttl
end

-- Helper function to split line into pattern and owners section
---@param input string The line to split
---@return LineParts parts The split parts
local function split_line_parts(input)
  ---@type LineParts
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
---@param owners_text string The owners text to parse
---@return string[] owners List of owner names
local function extract_owners(owners_text)
  ---@type string[]
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
---@param pattern string CODEOWNERS pattern
---@return string path Converted filesystem path
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
---@param line string Line to parse
---@return string|nil pattern File pattern or nil if invalid
---@return string[]|nil owners List of owners or nil if invalid
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
---@return CodeownersEntry[]|nil data Parsed CODEOWNERS data
---@return string|nil error Error message if failed
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

  ---@type CodeownersEntry[]
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
---@param owner_predicate fun(owner: string): boolean Function to test if owner matches
---@param description string Description for error messages
---@return string[]|nil directories List of matching directories or nil on error
local function find_directories_matching_owner(owner_predicate, description)
  local data, err = load_codeowners_data()
  if not data then
    vim.notify(err, vim.log.levels.ERROR)
    return nil
  end

  ---@type string[]
  local directories = {}
  ---@type table<string, boolean>
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
---@param search_config SearchConfig Configuration for the search
local function run_command(cmd, dir)
  local job = vim.system(cmd, { cwd = dir, text = true })
  if not job then
    return 1, {}, { "Failed to start command" }
  end

  local result = job:wait()
  if not result then
    return 1, {}, { "Command terminated unexpectedly" }
  end

  local stdout_lines = {}
  if result.stdout and result.stdout ~= "" then
    for line in vim.gsplit(result.stdout, "\n", { plain = true, trimempty = true }) do
      table.insert(stdout_lines, line)
    end
  end

  local stderr_lines = {}
  if result.stderr and result.stderr ~= "" then
    for line in vim.gsplit(result.stderr, "\n", { plain = true, trimempty = true }) do
      table.insert(stderr_lines, line)
    end
  end

  return result.code or 0, stdout_lines, stderr_lines
end

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

    if search_config.extra_args then
      vim.list_extend(cmd, search_config.extra_args)
    end

    table.insert(cmd, search_config.pattern)
    table.insert(cmd, dir)

    local exit_code, output = run_command(cmd, vim.uv.cwd())

    if exit_code == 0 then
      if search_config.process_output then
        search_config.process_output(output, results, dir)
      else
        vim.list_extend(results, output)
      end
    elseif exit_code ~= 1 then
      table.insert(errors, {
        dir = dir,
        code = exit_code,
        output = output,
      })
    end
  end

  if #results == 0 then
    local msg = #errors > 0
        and string.format("No %s found (%d directories had errors)", search_config.result_type, #errors)
      or string.format("No %s found in %d directories", search_config.result_type, total)
    print(msg)
    return
  end

  local items = {}
  local base_dir = vim.uv.cwd()

  for _, line in ipairs(results) do
    local item = create_qf_item(line, base_dir, search_config.result_type)
    if item then
      table.insert(items, item)
    end
  end

  if #items == 0 then
    print("Unable to parse results into quickfix entries")
    return
  end

  vim.fn.setqflist({}, " ", {
    title = search_config.title,
    items = items,
    directory = base_dir,
  })

  print(string.format("Found %d %s in %d directories", #items, search_config.result_type, total))
  vim.cmd("copen")
end

-- Public API Functions

-- Search for code patterns in directories owned by teams (substring match)
---@param team string Team name to search for (substring match)
---@param search_pattern string Pattern to search for in code
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
---@param team string Team name to search for (substring match)
---@param file_pattern string Pattern to search for in filenames
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
    process_output = process_file_output,
  })
end

-- Search for code patterns in directories owned by teams (regex match)
---@param owner_regex string Lua pattern to match owner names
---@param search_pattern string Pattern to search for in code
function M.owner_code_grep_pattern(owner_regex, search_pattern)
  if not owner_regex or owner_regex == "" or not search_pattern or search_pattern == "" then
    vim.notify("Usage: OwnerCodeGrepPattern <owner-regex> <search-pattern>", vim.log.levels.ERROR)
    return
  end

  local valid, err = validate_and_cache_regex(owner_regex)
  if not valid then
    vim.notify("Invalid regex pattern: " .. err, vim.log.levels.ERROR)
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
---@param owner_regex string Lua pattern to match owner names
---@param file_pattern string Pattern to search for in filenames
function M.owner_code_fd_pattern(owner_regex, file_pattern)
  if not owner_regex or owner_regex == "" or not file_pattern or file_pattern == "" then
    vim.notify("Usage: OwnerCodeFdPattern <owner-regex> <file-pattern>", vim.log.levels.ERROR)
    return
  end

  local valid, err = validate_and_cache_regex(owner_regex)
  if not valid then
    vim.notify("Invalid regex pattern: " .. err, vim.log.levels.ERROR)
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
    process_output = process_file_output,
  })
end

-- Utility function to list all owners and their directories
function M.list_owners()
  local data, err = load_codeowners_data()
  if not data then
    if err then
      vim.notify(err, vim.log.levels.ERROR)
    end
    return
  end

  ---@type table<string, string[]>
  local owner_map = {}
  for _, entry in ipairs(data) do
    for _, owner in ipairs(entry.owners) do
      if not owner_map[owner] then
        owner_map[owner] = {}
      end
      table.insert(owner_map[owner], entry.path)
    end
  end

  ---@type string[]
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
---@param opts CodeownersConfig|nil User configuration options
function M.setup(opts)
  if opts then
    M.config = vim.tbl_deep_extend("force", M.config, opts)
  end
end

return M
