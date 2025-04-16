local M = {}

-- Helper function to locate CODEOWNERS file
local function find_codeowners_file()
  local files = vim.fs.find(".github/CODEOWNERS", { upward = true })
  if #files == 0 then
    return nil, nil
  end
  return files[1]
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
      skip_next = true
    elseif char == " " and in_pattern then
      -- First unescaped space marks end of pattern
      in_pattern = false
      result.pattern = table.concat(pattern_chars)
      result.owners_text = input:sub(i)
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
  for owner in owners_text:gmatch("%S+") do
    table.insert(owners_list, owner)
  end
  return owners_list
end

-- Helper function to unescape and normalize pattern
local function normalize_pattern(pattern)
  return pattern:gsub("\\(.)", "%1"):gsub("^/", "")
end

M.parse_codeowners_line = function(line)
  -- Skip comments and empty lines
  if line:match("^%s*#") or line:match("^%s*$") then
    return nil
  end

  -- Process the line
  local parts = split_line_parts(line)
  local file_pattern = normalize_pattern(parts.pattern)
  local owners = extract_owners(parts.owners_text)

  return file_pattern, owners
end

-- Generic directory finder with predicate
local function find_directories_matching_owner(owner_predicate)
  local codeowners_file = ".github/CODEOWNERS"

  if vim.fn.filereadable(codeowners_file) ~= 1 then
    vim.notify("CODEOWNERS file not found at: " .. codeowners_file, vim.log.levels.ERROR)
    return nil
  end

  local lines = vim.fn.readfile(codeowners_file)
  local directories = {}

  for _, line in ipairs(lines) do
    local pattern, owners = M.parse_codeowners_line(line)
    if pattern and owners then
      for _, owner in ipairs(owners) do
        if owner_predicate(owner) then
          table.insert(directories, pattern)
          break
        end
      end
    end
  end

  if #directories == 0 then
    vim.notify("No directories found matching owner predicate", vim.log.levels.WARN)
    return nil
  end

  return directories
end

-- Substring matching (original functionality)
local function find_team_directories(team)
  return find_directories_matching_owner(function(owner)
    return string.find(owner, team, 1, true) ~= nil
  end)
end

-- Regex pattern matching (new functionality)
local function find_team_directories_by_regex(regex_pattern)
  return find_directories_matching_owner(function(owner)
    return owner:match(regex_pattern) ~= nil
  end)
end

local function execute_search(command, team_finder, pattern_arg, search_type)
  local directories = team_finder()
  if not directories then
    return
  end

  local results = {}
  local had_errors = false
  local is_fd = command[1] == "fd"

  for _, dir in ipairs(directories) do
    local cmd = vim.list_extend({}, command)
    table.insert(cmd, vim.fn.shellescape(pattern_arg))
    table.insert(cmd, vim.fn.shellescape(dir))

    if is_fd then
      table.insert(cmd, "--absolute-path")
    end

    local cmd_str = table.concat(cmd, " ")
    local output = vim.fn.systemlist(cmd_str)
    local exit_code = vim.v.shell_error

    if exit_code == 0 then
      if is_fd then
        for _, line in ipairs(output) do
          table.insert(results, line:gsub("%s*$", ""))
        end
      else
        vim.list_extend(results, output)
      end
    elseif exit_code == 1 then
      -- No matches in this directory, continue
    else
      had_errors = true
      print(command[1] .. " error searching " .. dir .. " (code " .. exit_code .. ")")
    end
  end

  if #results == 0 then
    local msg = had_errors and ("No " .. search_type .. " found (some directories had errors)")
      or ("No " .. search_type .. " found")
    print(msg)
    return
  end

  vim.fn.setqflist({}, " ", {
    lines = results,
    efm = is_fd and "%f" or "%f:%l:%c:%m",
  })
  vim.cmd("copen")
end

-- Original commands (substring match)
M.owner_code_grep = function(team, search_pattern)
  if not team or not search_pattern then
    vim.notify("Usage: OwnerCodeGrep <team> <search-pattern>", vim.log.levels.ERROR)
    return
  end
  execute_search({ "rg", "--vimgrep", "--hidden" }, function()
    return find_team_directories(team)
  end, search_pattern, "matches")
end

M.owner_code_fd = function(team, file_pattern)
  if not team or not file_pattern then
    vim.notify("Usage: OwnerCodeFd <team> <file-pattern>", vim.log.levels.ERROR)
    return
  end
  execute_search({ "fd", "--color=never", "--type=file", "--hidden" }, function()
    return find_team_directories(team)
  end, file_pattern, "files")
end

-- New regex pattern commands
M.owner_code_grep_pattern = function(team_regex, search_pattern)
  if not team_regex or not search_pattern then
    vim.notify("Usage: OwnerCodeGrepPattern <owner-regex> <search-pattern>", vim.log.levels.ERROR)
    return
  end
  execute_search({ "rg", "--vimgrep", "--hidden" }, function()
    return find_team_directories_by_regex(team_regex)
  end, search_pattern, "matches")
end

M.owner_code_fd_pattern = function(team_regex, file_pattern)
  if not team_regex or not file_pattern then
    vim.notify("Usage: OwnerCodeFdPattern <owner-regex> <file-pattern>", vim.log.levels.ERROR)
    return
  end
  execute_search({ "fd", "--color=never", "--type=file", "--hidden" }, function()
    return find_team_directories_by_regex(team_regex)
  end, file_pattern, "files")
end

return M
