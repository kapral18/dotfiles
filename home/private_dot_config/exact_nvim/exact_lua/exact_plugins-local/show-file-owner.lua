local M = {}

local function find_codeowners_file()
  local current_file = vim.api.nvim_buf_get_name(0)
  local current_dir = vim.fn.fnamemodify(current_file, ":h")

  while current_dir ~= "/" do
    local codeowners_path = current_dir .. "/.github/CODEOWNERS"
    if vim.fn.filereadable(codeowners_path) == 1 then
      return codeowners_path
    end
    current_dir = vim.fn.fnamemodify(current_dir, ":h")
  end
  return nil
end

local function glob_to_lua_pattern(glob)
  return glob:gsub("%.", "%%."):gsub("%*", ".*"):gsub("%?", "."):gsub("^/", "")
end

local function escape_non_lua_pattern_chars(pattern)
  return pattern
    :gsub("%%", "%%%%")
    :gsub("%.", "%%.")
    :gsub("%+", "%%+")
    :gsub("%-", "%%-")
    :gsub("%(", "%%(")
    :gsub("%)", "%%)")
    :gsub("%[", "%%[")
    :gsub("%]", "%%]")
    :gsub("%^", "%%^")
    :gsub("%$", "%%$")
    :gsub("%?", "%%?")
    :gsub("%*", "%%*")
end

local function parse_codeowners(file_path)
  local codeowners = {}
  for line in io.lines(file_path) do
    if not line:match("^%s*#") and not line:match("^%s*$") then
      local pattern, owners = line:match("([^%s]+)%s+(.+)")
      if pattern and owners then
        local escaped_pattern = escape_non_lua_pattern_chars(pattern)
        local globbed_pattern = glob_to_lua_pattern(escaped_pattern)
        table.insert(codeowners, {
          pattern = globbed_pattern,
          owners = owners,
          specificity = #globbed_pattern,
        })
      end
    end
  end
  -- Sort patterns by specificity (longer patterns first)
  table.sort(codeowners, function(a, b)
    return a.specificity > b.specificity
  end)
  return codeowners
end

local function find_owner_async(file_path, codeowners, callback)
  local relative_path = vim.fn.fnamemodify(file_path, ":.")

  -- Process patterns in batches
  local batch_size = 500
  local function process_batch(start_index)
    local end_index = math.min(start_index + batch_size - 1, #codeowners)
    for i = start_index, end_index do
      local entry = codeowners[i]
      if relative_path:match(entry.pattern) then
        callback(entry.owners)
        return
      end
    end

    if end_index < #codeowners then
      vim.schedule(function()
        process_batch(end_index + 1)
      end)
    else
      callback(nil)
    end
  end

  process_batch(1)
end

function M.show_file_owner()
  local codeowners_file = find_codeowners_file()
  if not codeowners_file then
    vim.notify("CODEOWNERS file not found", vim.log.levels.WARN)
    return
  end

  local codeowners = parse_codeowners(codeowners_file)
  local current_file = vim.api.nvim_buf_get_name(0)

  find_owner_async(current_file, codeowners, function(owner)
    if owner then
      vim.notify("File owner(s): " .. owner, vim.log.levels.INFO)
    else
      vim.notify("No owner found for this file", vim.log.levels.WARN)
    end
  end)
end

return M
