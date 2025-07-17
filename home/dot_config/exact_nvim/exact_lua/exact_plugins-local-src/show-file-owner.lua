local common_utils = require("utils.common")

local M = {}

---@class CodeOwnersEntry
---@field pattern string
---@field owners string
---@field specificity integer

---@class CodeOwnersCache
---@field codeowners_file string|nil Path to the CODEOWNERS file
---@field codeowners_data CodeOwnersEntry[]|nil Parsed CODEOWNERS data
---@field owner_cache table<string, string> Cache for file owner lookups
---@field last_modified integer|nil Last modified time of the CODEOWNERS file

-- Cache for parsed CODEOWNERS and owner lookups
---@type CodeOwnersCache
local cache = {
  codeowners_file = nil,
  codeowners_data = nil,
  owner_cache = {},
  last_modified = nil,
}

---@return string|nil
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

---@param glob string
---@return string
local function slash_stripped_glob_to_lua_pattern(glob)
  local lua_pattern = common_utils.glob_to_lua_pattern(glob)
  local lua_pattern_with_stripped_slash = lua_pattern:gsub("^/", "")

  return "^" .. lua_pattern_with_stripped_slash
end

---@return CodeOwnersEntry[]|nil
local function get_cached_codeowners()
  local codeowners_file = find_codeowners_file()
  if not codeowners_file then
    return nil
  end

  -- Check if cache is still valid
  local stat = vim.uv.fs_stat(codeowners_file)
  if not stat then
    return nil
  end

  local modified_time = stat.mtime.sec
  if cache.codeowners_file == codeowners_file and cache.last_modified == modified_time and cache.codeowners_data then
    return cache.codeowners_data
  end

  -- Parse and cache CODEOWNERS
  local codeowners = {}
  for
    line --[[@as string ]]
  in io.lines(codeowners_file) do
    line = line --[[ @as string ]]
    if not line:match("^%s*#") and not line:match("^%s*$") then
      local pattern, rest = line:match("([^%s]+)%s+(.+)")
      if pattern and rest then
        -- Extract owners by matching everything that looks like an owner (@username or team)
        -- until we hit a comment that's clearly a comment (# followed by space or text that's not an owner)
        local owners_part = ""
        local i = 1
        while i <= #rest do
          local char = rest:sub(i, i)
          if char == "#" then
            -- Check if this # is followed by a space or end of line (indicating a comment)
            local next_char = rest:sub(i + 1, i + 1)
            if next_char == "" or next_char:match("%s") then
              break -- This is a comment, stop here
            end
          end
          owners_part = owners_part .. char
          i = i + 1
        end

        owners_part = owners_part:gsub("%s+$", "") -- trim trailing whitespace
        if owners_part ~= "" then
          local globbed_pattern = slash_stripped_glob_to_lua_pattern(pattern)
          table.insert(codeowners, {
            pattern = globbed_pattern,
            owners = owners_part,
            specificity = #globbed_pattern,
          })
        end
      end
    end
  end

  -- Sort patterns by specificity (longer patterns first)
  table.sort(codeowners, function(a, b)
    return a.specificity > b.specificity
  end)

  -- Update cache
  cache.codeowners_file = codeowners_file
  cache.codeowners_data = codeowners
  cache.last_modified = modified_time
  cache.owner_cache = {} -- Clear owner cache when CODEOWNERS changes

  return codeowners
end

-- Fast synchronous owner lookup with caching
---@param file_path string
---@return string|nil
function M.get_file_owner(file_path)
  if not file_path or file_path == "" then
    return nil
  end

  -- Check cache first
  if cache.owner_cache[file_path] then
    return cache.owner_cache[file_path]
  end

  local codeowners = get_cached_codeowners()
  if not codeowners then
    return nil
  end

  local relative_path = vim.fn.fnamemodify(file_path, ":.")

  for _, entry in ipairs(codeowners) do
    if relative_path:match(entry.pattern) then
      cache.owner_cache[file_path] = entry.owners
      return entry.owners
    end
  end

  cache.owner_cache[file_path] = nil
  return nil
end

function M.show_file_owner()
  local current_file = vim.api.nvim_buf_get_name(0)
  local owner = M.get_file_owner(current_file)

  if owner then
    vim.notify("File owner(s): " .. owner, vim.log.levels.INFO)
  else
    vim.notify("No owner found for this file", vim.log.levels.WARN)
  end
end

-- Format owner string for display in limited space
---@param owner_string string
---@param max_width integer Maximum width for the formatted string
---@return string|nil
function M.format_owner_for_preview(owner_string, max_width)
  if not owner_string then
    return nil
  end

  max_width = max_width or 30

  -- Extract individual owners (typically @username or team names)
  local owners = {}
  for owner in owner_string:gmatch("@?([^%s]+)") do
    table.insert(owners, owner:match("^@") and owner or "@" .. owner)
  end

  if #owners == 0 then
    return owner_string:sub(1, max_width)
  end

  local formatted = table.concat(owners, " ")
  if #formatted <= max_width then
    return formatted
  end

  -- If too long, show first owner + count
  return owners[1] .. (#owners > 1 and " +" .. (#owners - 1) .. "" or "")
end

return M
