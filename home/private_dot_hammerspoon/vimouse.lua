-- Original Implementation Based on: https://github.com/tweekmonster/hammerspoon-vimouse/blob/master/vimouse.lua
--
-- Vi Mouse
--
-- This module provides a Vi-like mouse control mode for Hammerspoon. It allows
-- you to control the mouse cursor using Vi-like keybindings, including
-- grid-based navigation and mouse events.
--
-- Main Features:
-- <cmd-a> toggles Vi Mouse mode.
-- h/j/k/l moves the mouse cursor by 20 pixels.
-- alt-h/j/k/l moves the mouse cursor by 100 pixels.
-- shift-h/j/k/l moves the mouse cursor by 5 pixels.
-- <return or space or m> sends left mousedown. Releasing <return or space or m> sends left mouse up.
-- Holding <return or space or m> and pressing h/j/k/l is mouse dragging.
-- Tapping <return or space or m> quickly sends double and triple clicks.
-- Holding ctrl-<return or space or m> sends right mouse events.
-- <c-j/k> sends the scroll wheel event.
-- Holding <c-j/k> speeds up the scrolling.
-- <esc> or <cmd-a> ends Vi Mouse mode.
--
-- Grid Navigation:
-- <g> enters or resets grid mode from within Vi Mouse mode.
-- <cmd-g> activates or resets grid mode from outside of Vi Mouse mode.
-- <q/w/e/a/s/d/z/x/c> moves the mouse to the corresponding grid cell.
-- <f> zooms out to the previous grid level.
-- <esc> or <cmd-a> exits grid mode.

local eventTypes = hs.eventtap.event.types
local eventPropTypes = hs.eventtap.event.properties
local keycodes = hs.keycodes.map
local drawing = require("hs.drawing")

-- Configuration
local GRID_SIZE = 3
local GRID_HINTS = {
  [keycodes["q"]] = { col = 0, row = 0 },
  [keycodes["w"]] = { col = 1, row = 0 },
  [keycodes["e"]] = { col = 2, row = 0 },
  [keycodes["a"]] = { col = 0, row = 1 },
  [keycodes["s"]] = { col = 1, row = 1 },
  [keycodes["d"]] = { col = 2, row = 1 },
  [keycodes["z"]] = { col = 0, row = 2 },
  [keycodes["x"]] = { col = 1, row = 2 },
  [keycodes["c"]] = { col = 2, row = 2 },
}
local GRID_COLORS = {
  stroke = { red = 0.2, green = 0.8, blue = 0.2, alpha = 0.7 },
  text = { red = 1, green = 1, blue = 1, alpha = 0.9 },
}

local gridStack = {}
local currentGrid = nil
local isMouseModeActive = false
local gridEntryMode = nil
local scrollAcceleration = 0

-- Proportional scaling parameters
local BASE_TEXT_SIZE = 28
local TEXT_SCALE_FACTOR = 0.8
local MIN_TEXT_SIZE = 12
local BASE_STROKE_WIDTH = 2

local function postEvent(et, coords, modkeys, clicks)
  local e = hs.eventtap.event.newMouseEvent(et, coords, modkeys)
  e:setProperty(eventPropTypes.mouseEventClickState, math.min(clicks, 3))
  e:post()
end

local function createGridOverlay(boundary, scale)
  local elements = {}
  local cellW, cellH = boundary.w / GRID_SIZE, boundary.h / GRID_SIZE

  local textSize = math.max(MIN_TEXT_SIZE, BASE_TEXT_SIZE * (TEXT_SCALE_FACTOR ^ (scale - 1)))
  local strokeWidth = math.max(1, BASE_STROKE_WIDTH * (TEXT_SCALE_FACTOR ^ (scale - 1)))

  for col = 0, GRID_SIZE - 1 do
    for row = 0, GRID_SIZE - 1 do
      local rect = drawing.rectangle({
        x = boundary.x + col * cellW,
        y = boundary.y + row * cellH,
        w = cellW,
        h = cellH,
      })
      rect:setStrokeColor(GRID_COLORS.stroke)
      rect:setFill(false)
      rect:setStrokeWidth(strokeWidth)

      local hintKeys = { "q", "w", "e", "a", "s", "d", "z", "x", "c" }
      local hint = hintKeys[row * GRID_SIZE + col + 1]
      local text = drawing.text({
        x = boundary.x + col * cellW + cellW * 0.05,
        y = boundary.y + row * cellH + cellH * 0.05,
        w = cellW * 0.9,
        h = cellH * 0.9,
      }, hint:upper())
      text:setTextSize(textSize)
      text:setTextColor(GRID_COLORS.text)
      text:setTextStyle({ paragraphStyle = { alignment = "center" } })

      table.insert(elements, rect)
      table.insert(elements, text)
    end
  end
  return elements
end

local function showGrid(boundary)
  local scale = #gridStack + 1
  if currentGrid then
    for _, element in ipairs(currentGrid) do
      element:delete()
    end
  end
  currentGrid = createGridOverlay(boundary, scale)
  for _, element in ipairs(currentGrid) do
    element:show()
  end
end

local function cleanupAll()
  if currentGrid then
    for _, element in ipairs(currentGrid) do
      element:delete()
    end
    currentGrid = nil
  end
  gridStack = {}

  if gridEntryMode == "direct" then
    isMouseModeActive = false
  end
  gridEntryMode = nil
  scrollAcceleration = 0
end

local function handleGridKey(code)
  if not GRID_HINTS[code] then
    return false
  end

  local current = gridStack[#gridStack]
  local cellW = current.boundary.w / GRID_SIZE
  local cellH = current.boundary.h / GRID_SIZE
  local col, row = GRID_HINTS[code].col, GRID_HINTS[code].row

  local newBoundary = {
    x = current.boundary.x + col * cellW,
    y = current.boundary.y + row * cellH,
    w = cellW,
    h = cellH,
  }

  hs.mouse.absolutePosition({
    x = newBoundary.x + newBoundary.w / 2,
    y = newBoundary.y + newBoundary.h / 2,
  })

  table.insert(gridStack, {
    boundary = newBoundary,
    elements = currentGrid,
  })
  showGrid(newBoundary)
  return true
end

local function enterGridMode(mode)
  local screen = hs.mouse.getCurrentScreen():frame()
  gridStack = { { boundary = { x = screen.x, y = screen.y, w = screen.w, h = screen.h } } }
  gridEntryMode = mode
  showGrid(gridStack[1].boundary)

  if mode == "direct" then
    hs.alert("Grid Mode Active")
  end
end

local function exitGridMode()
  cleanupAll()
  if gridEntryMode == "direct" then
    hs.alert("Grid Mode Off")
  end
end

local function handleGridNavigation(event)
  local code = event:getKeyCode()

  if #gridStack > 0 then
    if event:getType() == eventTypes.keyDown then
      if code == keycodes["f"] then
        table.remove(gridStack)
        if #gridStack > 0 then
          local prev = gridStack[#gridStack]
          showGrid(prev.boundary)
          hs.mouse.absolutePosition({
            x = prev.boundary.x + prev.boundary.w / 2,
            y = prev.boundary.y + prev.boundary.h / 2,
          })
        else
          exitGridMode()
        end
        return true
      else
        return handleGridKey(code)
      end
    end
    return true
  end
  return false
end

-- Mouse mode tap (original functionality)
local mouseTap = hs.eventtap.new({ eventTypes.keyDown, eventTypes.keyUp }, function(event)
  if not isMouseModeActive then
    return false
  end

  local code = event:getKeyCode()
  local flags = event:getFlags()
  local coords = hs.mouse.absolutePosition()
  local repeating = event:getProperty(eventPropTypes.keyboardEventAutorepeat)

  -- Handle grid navigation first
  if handleGridNavigation(event) then
    return true
  end

  -- Exit handling
  if code == keycodes.escape then
    isMouseModeActive = false
    cleanupAll()
    hs.alert("Vi Mouse Off")
    return true
  end

  -- Scrolling handling
  if (code == keycodes["j"] or code == keycodes["k"]) and flags.ctrl then
    if event:getType() == eventTypes.keyDown then
      scrollAcceleration = (repeating ~= 0) and (scrollAcceleration + 1) or 1
      local scroll_mul = 1 + math.log(scrollAcceleration)
      local delta = (code == keycodes["j"]) and math.ceil(-8 * scroll_mul) or math.floor(8 * scroll_mul)

      hs.eventtap.event.newScrollEvent({ 0, delta }, flags, "pixel"):post()
    end
    return true
  end

  -- Original mouse functionality
  if code == keycodes["return"] or code == keycodes.space or code == keycodes.m then
    local btn = flags.ctrl and "right" or "left"
    if event:getType() == eventTypes.keyUp then
      postEvent(eventTypes[btn .. "MouseUp"], coords, flags, 1)
    else
      postEvent(eventTypes[btn .. "MouseDown"], coords, flags, 1)
    end
    return true
  elseif event:getType() == eventTypes.keyDown then
    -- Grid activation from mouse mode
    if code == keycodes["g"] then
      enterGridMode("mouse")
      return true
    end

    local mul = flags.alt and 5 or 1
    local step = flags.shift and 5 or 20
    local x, y = 0, 0

    if code == keycodes["h"] then
      x = -step * mul
    elseif code == keycodes["l"] then
      x = step * mul
    elseif code == keycodes["j"] then
      y = step * mul
    elseif code == keycodes["k"] then
      y = -step * mul
    end

    if x ~= 0 or y ~= 0 then
      coords.x = coords.x + x
      coords.y = coords.y + y
      hs.mouse.absolutePosition(coords)
      return true
    end
  end

  return false
end)

-- Toggle mouse mode (cmd+a)
hs.hotkey.bind("cmd", "a", function()
  isMouseModeActive = not isMouseModeActive
  if isMouseModeActive then
    hs.alert("Vi Mouse On")
    mouseTap:start()
  else
    cleanupAll()
    hs.alert("Vi Mouse Off")
    mouseTap:stop()
  end
end)

-- Direct grid mode entry (cmd+g)
hs.hotkey.bind("cmd", "g", function()
  if not isMouseModeActive then
    enterGridMode("direct")
    isMouseModeActive = true -- Allow mouse movement after grid selection
  end
end)

-- Global escape handler
hs.hotkey.bind({}, "escape", function()
  if isMouseModeActive or #gridStack > 0 then
    isMouseModeActive = false
    cleanupAll()
    hs.alert("Mode Deactivated")
  end
end)
