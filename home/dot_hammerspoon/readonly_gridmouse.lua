-- Non-grid implementation based on: https://github.com/tweekmonster/hammerspoon-vimouse/blob/master/vimouse.lua
--
-- GridMouse
--
-- This module provides a Vi-like mouse control mode for Hammerspoon. It allows
-- you to control the mouse cursor using Vi-like keybindings, including
-- grid-based navigation and mouse events.
--
-- Main Features:
-- <cmd-d> toggles GridMouse mode.
-- h/j/k/l moves the mouse cursor by 20 pixels.
-- alt-h/j/k/l moves the mouse cursor by 100 pixels.
-- shift-h/j/k/l moves the mouse cursor by 5 pixels.
-- <return or space or m> sends left mousedown. Releasing <return or space or m> sends left mouse up.
-- Holding <return or space or m> and pressing h/j/k/l is mouse dragging.
-- Tapping <return or space or m> quickly sends double and triple clicks.
-- Holding ctrl-<return or space or m> sends right mouse events.
-- <c-j/k> sends the scroll wheel event.
-- Holding <c-j/k> speeds up the scrolling.
-- <esc> or <cmd-d> ends GridMouse mode.
--
-- Grid Navigation:
-- <g> enters grid mode from within GridMouse mode.
-- <cmd-g> activates grid mode from outside of GridMouse mode.
-- <q/w/e/a/s/d/z/x/c> moves the mouse to the corresponding grid cell.
-- <f> zooms out to the previous grid level.
-- <esc> or <cmd-d> exits grid mode.
-- clicking in grid mode sends a mouse event to the clicked position and exits grid mode.

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
local BASE_TEXT_SIZE = 28
local TEXT_SCALE_FACTOR = 0.8
local MIN_TEXT_SIZE = 12
local BASE_STROKE_WIDTH = 2
local DRAG_THRESHOLD = 5 -- Pixels to move before considering it a drag
local DRAG_DELAY = 0.2 -- Seconds to wait before drag starts

-- Finite State Machine
local FSM = {
  states = {
    INACTIVE = {
      transitions = {
        activate_mouse = "MOUSE",
        activate_grid = "GRID",
      },
    },
    MOUSE = {
      transitions = {
        deactivate = "INACTIVE",
        activate_grid = "GRID",
      },
    },
    GRID = {
      transitions = {
        deactivate = "PREVIOUS",
        zoom_out = "GRID",
      },
    },
  },
  current = "INACTIVE",
  context = {
    grid = {
      stack = {},
      current = nil,
      previous_state = "INACTIVE",
    },
    drag = {
      active = false,
      timer = nil,
      button = "left",
      start_pos = nil,
      delay_timer = nil,
    },
    scroll = {
      acceleration = 0,
    },
  },
  modals = {
    escape = hs.hotkey.modal.new(),
  },
}

-- State Transition System
function FSM.transition(newState, ...)
  local prevState = FSM.current

  if newState == "PREVIOUS" then
    newState = FSM.context.grid.previous_state
  end

  -- Cleanup previous state
  if prevState == "GRID" then
    if FSM.context.grid.current then
      for _, element in ipairs(FSM.context.grid.current) do
        element:delete()
      end
      FSM.context.grid.current = nil
    end
    FSM.context.grid.stack = {}
  end

  -- Cancel any pending drags
  if FSM.context.drag.delay_timer then
    FSM.context.drag.delay_timer:stop()
    FSM.context.drag.delay_timer = nil
  end
  if FSM.context.drag.timer then
    FSM.context.drag.timer:stop()
    FSM.context.drag.timer = nil
  end
  FSM.context.drag.active = false
  FSM.context.drag.start_pos = nil

  -- State transition
  FSM.current = newState

  -- Enter actions
  if newState == "MOUSE" then
    hs.alert("Mouse Mode Active")
    FSM.mouseTap:start()
    FSM.modals.escape:enter()
  elseif newState == "GRID" then
    local screen = hs.mouse.getCurrentScreen():frame()
    FSM.context.grid.stack = { { boundary = screen } }
    FSM.context.grid.previous_state = prevState
    FSM.showGrid(screen)
    hs.alert("Grid Mode Active")
    FSM.modals.escape:enter()
    FSM.mouseTap:start()
  elseif newState == "INACTIVE" then
    hs.alert("Mode Deactivated")
    FSM.mouseTap:stop()
    FSM.modals.escape:exit()
  end
end

-- Grid Management
function FSM.createGridOverlay(boundary, scale)
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
      local text = drawing.text({
        x = boundary.x + col * cellW + cellW * 0.05,
        y = boundary.y + row * cellH + cellH * 0.05,
        w = cellW * 0.9,
        h = cellH * 0.9,
      }, hintKeys[row * GRID_SIZE + col + 1]:upper())
      text:setTextSize(textSize)
      text:setTextColor(GRID_COLORS.text)
      text:setTextStyle({ paragraphStyle = { alignment = "center" } })

      table.insert(elements, rect)
      table.insert(elements, text)
    end
  end
  return elements
end

function FSM.showGrid(boundary)
  if FSM.context.grid.current then
    for _, element in ipairs(FSM.context.grid.current) do
      element:delete()
    end
    FSM.context.grid.current = nil
  end

  FSM.context.grid.current = FSM.createGridOverlay(boundary, #FSM.context.grid.stack + 1)
  for _, element in ipairs(FSM.context.grid.current) do
    element:show()
  end
end

-- Event Handling
FSM.mouseTap = hs.eventtap.new({ eventTypes.keyDown, eventTypes.keyUp }, function(event)
  local code = event:getKeyCode()
  local flags = event:getFlags()
  local repeating = event:getProperty(eventPropTypes.keyboardEventAutorepeat)

  -- Global escape handling
  if code == keycodes.escape then
    if FSM.current == "GRID" then
      FSM.transition("PREVIOUS")
    else
      FSM.transition("INACTIVE")
    end
    return true
  end

  -- Grid navigation handling
  if FSM.current == "GRID" and event:getType() == eventTypes.keyDown then
    if code == keycodes["f"] then
      table.remove(FSM.context.grid.stack)
      if #FSM.context.grid.stack > 0 then
        local prev = FSM.context.grid.stack[#FSM.context.grid.stack]
        FSM.showGrid(prev.boundary)
        hs.mouse.absolutePosition({
          x = prev.boundary.x + prev.boundary.w / 2,
          y = prev.boundary.y + prev.boundary.h / 2,
        })
      else
        FSM.transition("PREVIOUS")
      end
      return true
    else
      local hint = GRID_HINTS[code]
      if hint then
        local current = FSM.context.grid.stack[#FSM.context.grid.stack]
        local cellW = current.boundary.w / GRID_SIZE
        local cellH = current.boundary.h / GRID_SIZE

        local newBoundary = {
          x = current.boundary.x + hint.col * cellW,
          y = current.boundary.y + hint.row * cellH,
          w = cellW,
          h = cellH,
        }

        hs.mouse.absolutePosition({
          x = newBoundary.x + newBoundary.w / 2,
          y = newBoundary.y + newBoundary.h / 2,
        })

        table.insert(FSM.context.grid.stack, {
          boundary = newBoundary,
          elements = FSM.context.grid.current,
        })
        FSM.showGrid(newBoundary)
        return true
      end
    end
  end

  -- Mouse controls (works in both MOUSE and GRID states)
  if FSM.current == "MOUSE" or FSM.current == "GRID" then
    -- Scrolling
    if (code == keycodes["j"] or code == keycodes["k"]) and flags.ctrl then
      if event:getType() == eventTypes.keyDown then
        FSM.context.scroll.acceleration = (repeating ~= 0) and (FSM.context.scroll.acceleration + 1) or 1
        local scroll_mul = 1 + math.log(FSM.context.scroll.acceleration)
        local delta = (code == keycodes["j"]) and math.ceil(-8 * scroll_mul) or math.floor(8 * scroll_mul)
        hs.eventtap.event.newScrollEvent({ 0, delta }, flags, "pixel"):post()
      end
      return true
    end

    -- Mouse buttons
    if code == keycodes["return"] or code == keycodes.space or code == keycodes.m then
      local btn = flags.ctrl and "right" or "left"

      if event:getType() == eventTypes.keyDown then
        -- Mouse down handling
        FSM.context.drag.start_pos = hs.mouse.absolutePosition()
        hs.eventtap.event.newMouseEvent(eventTypes[btn .. "MouseDown"], FSM.context.drag.start_pos, flags):post()

        -- Start drag delay timer
        FSM.context.drag.delay_timer = hs.timer.doAfter(DRAG_DELAY, function()
          -- Check if mouse has moved beyond threshold
          local current_pos = hs.mouse.absolutePosition()
          local dx = math.abs(current_pos.x - FSM.context.drag.start_pos.x)
          local dy = math.abs(current_pos.y - FSM.context.drag.start_pos.y)

          if dx > DRAG_THRESHOLD or dy > DRAG_THRESHOLD then
            FSM.context.drag.active = true
            FSM.context.drag.button = btn
            FSM.context.drag.timer = hs.timer.doWhile(function()
              return FSM.context.drag.active
            end, function()
              local currentPos = hs.mouse.absolutePosition()
              hs.eventtap.event.newMouseEvent(eventTypes[btn .. "MouseDragged"], currentPos, flags):post()
            end, 0.016)
          end
        end)
      else
        -- Mouse up handling
        local current_pos = hs.mouse.absolutePosition()

        -- Cleanup timers
        if FSM.context.drag.delay_timer then
          FSM.context.drag.delay_timer:stop()
          FSM.context.drag.delay_timer = nil
        end

        -- Post mouse up event
        hs.eventtap.event.newMouseEvent(eventTypes[btn .. "MouseUp"], current_pos, flags):post()

        -- Handle click if not dragged
        if not FSM.context.drag.active then
          -- Post additional click if within threshold
          local dx = math.abs(current_pos.x - FSM.context.drag.start_pos.x)
          local dy = math.abs(current_pos.y - FSM.context.drag.start_pos.y)
          if dx <= DRAG_THRESHOLD and dy <= DRAG_THRESHOLD then
            hs.eventtap.event.newMouseEvent(eventTypes[btn .. "MouseUp"], current_pos, flags):post()
          end
        end

        -- Cleanup drag state
        FSM.context.drag.active = false
        FSM.context.drag.start_pos = nil
        if FSM.context.drag.timer then
          FSM.context.drag.timer:stop()
          FSM.context.drag.timer = nil
        end

        if FSM.current == "GRID" then
          FSM.transition("PREVIOUS")
        end
      end
      return true
    end

    -- Mouse movement
    if event:getType() == eventTypes.keyDown then
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
        local currentPos = hs.mouse.absolutePosition()
        currentPos.x = currentPos.x + x
        currentPos.y = currentPos.y + y
        hs.mouse.absolutePosition(currentPos)

        if FSM.context.drag.active then
          hs.eventtap.event
            .newMouseEvent(eventTypes[FSM.context.drag.button .. "MouseDragged"], currentPos, flags)
            :post()
        end
        return true
      end
    end
  end

  -- Activate grid from mouse mode
  if FSM.current == "MOUSE" and event:getType() == eventTypes.keyDown and code == keycodes["g"] then
    FSM.transition("GRID")
    return true
  end

  return false
end)

-- Modal Bindings
FSM.modals.escape:bind("", "escape", function()
  if FSM.current == "GRID" then
    FSM.transition("PREVIOUS")
  else
    FSM.transition("INACTIVE")
  end
end)

-- Hotkey Bindings
hs.hotkey.bind("cmd", "d", function()
  if FSM.current == "INACTIVE" then
    FSM.transition("MOUSE")
  else
    FSM.transition("INACTIVE")
  end
end)

hs.hotkey.bind("cmd", "g", function()
  if FSM.current == "INACTIVE" then
    FSM.transition("GRID")
  end
end)

-- Terminal Compatibility
hs.urlevent.bind("openConsole", function()
  if FSM.current ~= "INACTIVE" then
    FSM.mouseTap:start()
  end
end)
