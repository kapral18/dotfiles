local M = {}

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

M.owner_folder_search = function(team, search_pattern)
  local parts = { team, search_pattern }
  if #parts < 2 then
    vim.notify("Usage: OwnerFolderSearch <team> <search-pattern>", vim.log.levels.ERROR)
    return
  end

  -- find codeowners file in the root of the project
  local codeowners_file = vim.fs.root(0, ".git") .. "/.github/CODEOWNERS"

  if not vim.fn.filereadable(codeowners_file) then
    vim.notify("CODEOWNERS file not found", vim.log.levels.ERROR)
    return
  end

  -- Read the codeowners file
  local lines = vim.fn.readfile(codeowners_file)

  local directories = {}

  -- Collect directories owned by the team (same as before)
  for _, line in ipairs(lines) do
    local pattern, owners = M.parse_codeowners_line(line)
    if pattern and owners then
      for _, owner in ipairs(owners) do
        if string.find(owner, team, 1, true) then
          table.insert(directories, pattern)
          break
        end
      end
    end
  end

  if #directories == 0 then
    vim.notify("No directories found for team: " .. team, vim.log.levels.WARN)
    return
  end

  local results = {}
  local had_errors = false

  for _, dir in ipairs(directories) do
    local cmd = { "rg", "--vimgrep", vim.fn.shellescape(search_pattern), vim.fn.shellescape(dir) }
    local exit_code
    local output

    -- Use explicit shell command form for better error handling
    local cmd_str = table.concat(cmd, " ")
    output = vim.fn.systemlist(cmd_str)
    exit_code = vim.v.shell_error

    if exit_code == 0 then
      vim.list_extend(results, output)
    elseif exit_code == 1 then
      -- No matches in this directory, continue
    else
      had_errors = true
      print("rg error searching " .. dir .. " (code " .. exit_code .. ")", vim.log.levels.ERROR)
    end
  end

  -- Handle final results
  if #results == 0 then
    local msg = had_errors and "No matches found (some directories had errors)" or "No matches found"
    print(msg, vim.log.levels.WARN)
    return
  end

  -- Populate quickfix list
  vim.fn.setqflist({}, " ", {
    lines = results,
    efm = "%f:%l:%c:%m",
  })
  vim.cmd("copen")
end

return M
