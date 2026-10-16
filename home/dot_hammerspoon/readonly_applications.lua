local M = {}
local applications = {}

local fold = require("search_text")

function M.refresh()
  applications = {}
  local seen = {}
  local function scan(path)
    local absolute = hs.fs.pathToAbsolute(path)
    if not absolute or seen[absolute] or hs.fs.attributes(absolute, "mode") ~= "directory" then
      return
    end
    seen[absolute] = true
    if absolute:lower():sub(-4) == ".app" then
      local name = absolute:match("([^/]+)$"):sub(1, -5)
      applications[#applications + 1] = {
        text = name,
        subText = absolute,
        app = absolute,
        searchName = fold(name),
      }
      return
    end
    -- Unreadable or concurrently removed folders must not break the launcher.
    pcall(function()
      for name in hs.fs.dir(absolute) do
        if name:sub(1, 1) ~= "." then
          scan(absolute .. "/" .. name)
        end
      end
    end)
  end
  for _, root in ipairs({
    "/Applications",
    "/System/Applications",
    os.getenv("HOME") .. "/Applications",
    "/System/Library/CoreServices/Applications",
    "/System/Library/CoreServices/Finder.app",
  }) do
    scan(root)
  end
end

function M.search(term)
  local query = fold(term)
  local choices = {}
  for _, app in ipairs(applications) do
    local name = app.searchName
    local matches = true
    for word in query:gmatch("%S+") do
      if not name:find(word, 1, true) then
        matches = false
        break
      end
    end
    if matches then
      choices[#choices + 1] = app
    end
  end
  local function rank(name)
    -- Names and query already use the same Unicode case/diacritic folding.
    return name == query and 1 or name:sub(1, #query) == query and 2 or 3
  end
  table.sort(choices, function(left, right)
    local a, b = rank(left.searchName), rank(right.searchName)
    if a ~= b then
      return a < b
    end
    if left.text ~= right.text then
      return left.text < right.text
    end
    return left.app < right.app
  end)
  return choices
end

return M
