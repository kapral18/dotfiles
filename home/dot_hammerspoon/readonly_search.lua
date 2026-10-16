local M = {}
local providers = { ud = require("urban_dictionary") }
local chooser
local generation = 0
local pending

local function invalidate()
  generation = generation + 1
  if pending then
    pending:stop()
    pending = nil
  end
end

local function current(version)
  return generation == version and chooser:isVisible()
end

local function message(text)
  chooser:choices({ { text = text, valid = false } })
end

local function commands(prefix)
  local choices = {}
  for keyword, provider in pairs(providers) do
    if keyword:sub(1, #prefix) == prefix then
      choices[#choices + 1] = {
        text = keyword .. " — " .. provider.title,
        subText = provider.hint,
        query = keyword .. " ",
      }
    end
  end
  table.sort(choices, function(left, right)
    return left.query < right.query
  end)
  if #choices == 0 then
    message("Unknown search keyword — use ud <word or phrase>")
    return
  end
  chooser:choices(choices)
end

local function query_changed(query)
  invalidate()
  local version = generation
  local keyword, term = query:match("^%s*(%S+)%s*(.-)%s*$")
  keyword = keyword and keyword:lower() or ""
  local provider = providers[keyword]
  if not provider then
    commands(keyword)
    return
  end
  if term == "" then
    message(provider.hint)
    return
  end
  message("Searching " .. provider.title .. "…")
  pending = hs.timer.doAfter(0.25, function()
    pending = nil
    provider.search(term, function(choices)
      if current(version) then
        chooser:choices(choices)
      end
    end, function()
      return current(version)
    end)
  end)
end

function M.show(query)
  if chooser:isVisible() then
    chooser:hide()
    return
  end
  invalidate()
  chooser:choices({}):query(query or ""):show()
  if query and query ~= "" then
    -- Cocoa selects seeded text after show returns; place the caret after it.
    local version = generation
    pending = hs.timer.doAfter(0, function()
      pending = nil
      if current(version) then
        hs.eventtap.keyStroke({}, "right", 0)
      end
    end)
  end
end

chooser = hs.chooser.new(function(choice)
  invalidate()
  if choice and choice.query then
    M.show(choice.query)
  elseif choice and choice.url then
    hs.urlevent.openURL(choice.url)
  end
end)
chooser:rows(8):width(55):placeholderText("Search — ud <word or phrase>")
chooser:queryChangedCallback(query_changed)
chooser:hideCallback(invalidate)

return M
