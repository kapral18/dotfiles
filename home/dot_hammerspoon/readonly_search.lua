local M = {}
local characters = require("characters")
local applications = require("applications")
local providers = {
  ud = require("urban_dictionary"),
  gh = require("github"),
  tr = require("translation"),
  emoji = characters.emoji,
  sym = characters.symbols,
}
local chooser
local panel_tap
local row_count = 0
local generation = 0
local pending
local cancel

local function invalidate()
  generation = generation + 1
  if pending then
    pending:stop()
    pending = nil
  end
  if cancel then
    cancel()
    cancel = nil
  end
end

local function current(version)
  return generation == version and chooser:isVisible()
end

-- Every list goes through here so keyboard navigation knows how many rows to wrap over.
local function set_choices(choices)
  row_count = #choices
  chooser:choices(choices)
end

local function message(text)
  set_choices({ { text = text, valid = false } })
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
  local apps = prefix ~= "" and applications.search(prefix) or {}
  for _, choice in ipairs(choices) do
    apps[#apps + 1] = choice
  end
  if #apps == 0 then
    message("No matching applications — use tr, gh, emoji, sym or ud for other searches")
    return
  end
  set_choices(apps)
end

local function query_changed(query)
  invalidate()
  local version = generation
  local keyword, term = query:match("^%s*(%S+)%s*(.-)%s*$")
  keyword = keyword and keyword:lower() or ""
  local provider = query:match("^%s*%S+%s") and providers[keyword]
  if not provider then
    commands(query:match("^%s*(.-)%s*$"):lower())
    return
  end
  if term == "" then
    message(provider.hint)
    return
  end
  message("Searching " .. provider.title .. "…")
  local function search()
    pending = nil
    cancel = provider.search(term, function(choices)
      if current(version) then
        set_choices(choices)
      end
    end, function()
      return current(version)
    end)
  end
  if provider.immediate then
    search()
  else
    pending = hs.timer.doAfter(0.25, search)
  end
end

function M.show(query)
  if chooser:isVisible() then
    chooser:hide()
    return
  end
  invalidate()
  applications.refresh()
  set_choices({})
  chooser:query(query or ""):show()
  panel_tap:start()
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
  if not choice or choice.valid == false then
    return
  end
  if choice.query then
    M.show(choice.query)
  elseif choice.url then
    hs.urlevent.openURL(choice.url)
  elseif choice.copy then
    if not hs.pasteboard.setContents(choice.copy) then
      hs.alert.show("Could not copy the selected text")
    end
  elseif choice.app then
    if not hs.fs.attributes(choice.app, "mode") or not hs.application.launchOrFocus(choice.app) then
      hs.alert.show("Application unavailable — reopen the panel to refresh")
    end
  end
end)
chooser:rows(8):width(55):placeholderText("Find apps, or use tr · gh · emoji · sym · ud")
chooser:queryChangedCallback(query_changed)
-- The chooser's own key monitors (Escape, arrows, Ctrl-N/P) do nothing while another app
-- is active, which is the usual case after the double-Command gesture. One keyDown tap owns
-- these keys instead. It consumes them only while the panel is visible, so even a close
-- path that skips cleanup cannot take keys from other apps. Physical ANSI key codes keep
-- the bindings on the same keys under any input layout.
local function move(step)
  if row_count > 0 then
    chooser:selectedRow((chooser:selectedRow() - 1 + step) % row_count + 1)
  end
end
local function close()
  chooser:cancel()
end
local function down()
  move(1)
end
local function up()
  move(-1)
end
local PLAIN = { [53] = close, [125] = down, [126] = up } -- Escape, Down, Up
local CONTROL = { [8] = close, [38] = down, [40] = up, [45] = down, [35] = up } -- C, J, K, N, P
panel_tap = hs.eventtap.new({ hs.eventtap.event.types.keyDown }, function(event)
  if not chooser:isVisible() then
    return false
  end
  local flags = event:getFlags()
  if flags.cmd or flags.alt or flags.shift then
    return false
  end
  -- Arrow events carry the fn flag, so it is ignored.
  local action = (flags.ctrl and CONTROL or PLAIN)[event:getKeyCode()]
  if not action then
    return false
  end
  action()
  return true
end)
chooser:hideCallback(function()
  invalidate()
  -- Stopping the tap from inside its own callback is avoided; the visibility check above
  -- already makes a still-running tap inert.
  hs.timer.doAfter(0, function()
    if not chooser:isVisible() then
      panel_tap:stop()
    end
  end)
end)

local previous_shutdown = hs.shutdownCallback
hs.shutdownCallback = function()
  invalidate()
  -- Native chooser GC clears callbacks without hiding the window.
  chooser:hide()
  panel_tap:stop()
  if previous_shutdown then
    previous_shutdown()
  end
end

return M
