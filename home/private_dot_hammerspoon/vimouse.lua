-- Credits: https://github.com/tweekmonster/hammerspoon-vimouse/blob/master/vimouse.lua
--
-- Save to ~/.hammerspoon
-- In ~/.hammerspoon/init.lua:
--    local vimouse = require('vimouse')
--    vimouse('cmd', 'm')
--
-- This sets cmd-m as the key that toggles Vi Mouse.
--
-- h/j/k/l moves the mouse cursor by 20 pixels.  Holding alt moves by 100
-- pixels, and holding shift moves by 5 pixels.
--
-- Pressing <return or space or m> sends left mouse down.  Releasing <return or space or m> sends left mouse
-- up.  Holding <return or space or m> and pressing h/j/k/l is mouse dragging.  Tapping
-- <return or space or m> quickly sends double and triple clicks.  Holding ctrl sends right
-- mouse events.
--
-- <c-j> and <c-k> sends the scroll wheel event.  Holding the keys will speed
-- up the scrolling.
--
-- Press <esc> or the configured toggle key to end Vi Mouse mode.

-- Final fully functional version with proper grid navigation and exit handling
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

local function postEvent(et, coords, modkeys, clicks)
  local e = hs.eventtap.event.newMouseEvent(et, coords, modkeys)
  e:setProperty(eventPropTypes.mouseEventClickState, math.min(clicks, 3))
  e:post()
end

local function createGridOverlay(boundary)
  local elements = {}
  local cellW, cellH = boundary.w / GRID_SIZE, boundary.h / GRID_SIZE

  for col = 0, GRID_SIZE - 1 do
    for row = 0, GRID_SIZE - 1 do
      -- Cell rectangle
      local rect = drawing.rectangle({
        x = boundary.x + col * cellW,
        y = boundary.y + row * cellH,
        w = cellW,
        h = cellH,
      })
      rect:setStrokeColor(GRID_COLORS.stroke)
      rect:setFill(false)
      rect:setStrokeWidth(2)

      -- Hint label
      local hintKeys = { "q", "w", "e", "a", "s", "d", "z", "x", "c" }
      local hint = hintKeys[row * GRID_SIZE + col + 1]
      local text = drawing.text({
        x = boundary.x + col * cellW + 15,
        y = boundary.y + row * cellH + 15,
        w = 40,
        h = 40,
      }, hint:upper())
      text:setTextSize(28)
      text:setTextColor(GRID_COLORS.text)

      table.insert(elements, rect)
      table.insert(elements, text)
    end
  end
  return elements
end

local function showGrid(boundary)
  if currentGrid then
    for _, element in ipairs(currentGrid) do
      element:delete()
    end
  end
  currentGrid = createGridOverlay(boundary)
  for _, element in ipairs(currentGrid) do
    element:show()
  end
end

local function cleanupAll()
  -- Cleanup grid state
  if currentGrid then
    for _, element in ipairs(currentGrid) do
      element:delete()
    end
    currentGrid = nil
  end
  gridStack = {}

  -- Reset mouse mode
  isMouseModeActive = false
end

local function handleGridKey(code)
  if not GRID_HINTS[code] then
    return false
  end

  -- Calculate new grid boundary
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

  -- Update mouse position
  hs.mouse.absolutePosition({
    x = newBoundary.x + newBoundary.w / 2,
    y = newBoundary.y + newBoundary.h / 2,
  })

  -- Push new grid state
  table.insert(gridStack, {
    boundary = newBoundary,
    elements = currentGrid,
  })
  showGrid(newBoundary)
  return true
end

local function vimouse(tmod, tkey)
  local tap = hs.eventtap.new({ eventTypes.keyDown, eventTypes.keyUp }, function(event)
    if not isMouseModeActive then
      return false
    end

    local code = event:getKeyCode()
    local flags = event:getFlags()
    local coords = hs.mouse.absolutePosition()

    -- Exit handling (works in any mode)
    if code == keycodes.escape or (code == keycodes[tkey] and flags[tmod]) then
      cleanupAll()
      hs.alert("Vi Mouse Off")
      return true
    end

    -- Grid navigation handling
    if #gridStack > 0 then
      if event:getType() == eventTypes.keyDown then
        -- Zoom out with F
        if code == keycodes["f"] then
          table.remove(gridStack) -- Remove current level
          if #gridStack > 0 then
            local prev = gridStack[#gridStack]
            showGrid(prev.boundary)
            hs.mouse.absolutePosition({
              x = prev.boundary.x + prev.boundary.w / 2,
              y = prev.boundary.y + prev.boundary.h / 2,
            })
          else
            cleanupAll()
          end
          return true
        else
          return handleGridKey(code)
        end
      end
      return false -- Allow other key processing
    end

    -- Original Vimouse functionality
    if code == keycodes["return"] or code == keycodes.space or code == keycodes.m then
      local btn = flags.ctrl and "right" or "left"
      local now = hs.timer.secondsSinceEpoch()
      local mousepress = 0

      if event:getType() == eventTypes.keyUp then
        postEvent(eventTypes[btn .. "MouseUp"], coords, flags, mousepress)
      else
        mousepress = 1
        postEvent(eventTypes[btn .. "MouseDown"], coords, flags, mousepress)
      end
      return true
    elseif event:getType() == eventTypes.keyDown then
      -- Grid activation
      if code == keycodes["g"] then
        local screen = hs.mouse.getCurrentScreen():frame()
        gridStack = {
          { boundary = { x = screen.x, y = screen.y, w = screen.w, h = screen.h } },
        }
        showGrid(gridStack[1].boundary)
        return true
      end

      -- Movement logic
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

  hs.hotkey.bind(tmod, tkey, function()
    if isMouseModeActive then
      cleanupAll()
      hs.alert("Vi Mouse Off")
    else
      isMouseModeActive = true
      hs.alert("Vi Mouse On")
      tap:start()
    end
  end)
end

return vimouse("cmd", "a")
