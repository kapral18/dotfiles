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
-- pixels, and holding alt moves by 5 pixels.
--
-- Pressing <return or space or m> sends left mouse down.  Releasing <return or space or m> sends left mouse
-- up.  Holding <return or space or m> and pressing h/j/k/l is mouse dragging.  Tapping
-- <return or space or m> quickly sends double and triple clicks.  Holding ctrl sends right
-- mouse events.
--
-- <c-y> and <c-e> sends the scroll wheel event.  Holding the keys will speed
-- up the scrolling.
--
-- Press <esc> or the configured toggle key to end Vi Mouse mode.

local eventTypes = hs.eventtap.event.types
local eventPropTypes = hs.eventtap.event.properties
local keycodes = hs.keycodes.map

local function postEvent(et, coords, modkeys, clicks)
  local e = hs.eventtap.event.newMouseEvent(et, coords, modkeys)
  if clicks > 3 then
    clicks = 3
  end
  e:setProperty(eventPropTypes.mouseEventClickState, clicks)
  e:post()
end

-- Helper to simulate mouse movement for Dock appearance
local function simulateMouseMovement(coords)
  hs.eventtap.event.newMouseEvent(eventTypes.mouseMoved, coords):post()
end

local function vimouse(tmod, tkey)
  -- local overlay = nil
  local log = hs.logger.new("vimouse", "debug")
  local tap = nil
  local orig_coords = nil
  local dragging = false
  local scrolling = 0
  local mousedown_time = 0
  local mousepress_time = 0
  local mousepress = 0
  local tapmods = { ["cmd"] = false, ["ctrl"] = false, ["alt"] = false, ["shift"] = false }

  if type(tmod) == "string" then
    tapmods[tmod] = true
  else
    for _, name in ipairs(tmod) do
      tapmods[name] = true
    end
  end

  tap = hs.eventtap.new({ eventTypes.keyDown, eventTypes.keyUp }, function(event)
    local code = event:getKeyCode()
    local flags = event:getFlags()
    local repeating = event:getProperty(eventPropTypes.keyboardEventAutorepeat)
    local coords = hs.mouse.absolutePosition()

    if (code == keycodes.tab or code == keycodes["`"]) and flags.cmd then
      return false
    end

    if code == keycodes["return"] or code == keycodes.space or code == keycodes.m then
      -- Mouse clicking
      if repeating ~= 0 then
        return true
      end

      local btn = "left"
      if flags.ctrl then
        btn = "right"
      end

      local now = hs.timer.secondsSinceEpoch()
      if now - mousepress_time > hs.eventtap.doubleClickInterval() then
        mousepress = 1
      end

      if event:getType() == eventTypes.keyUp then
        dragging = false
        postEvent(eventTypes[btn .. "MouseUp"], coords, flags, mousepress)
      elseif event:getType() == eventTypes.keyDown then
        dragging = true
        if now - mousedown_time <= 0.3 then
          mousepress = mousepress + 1
          mousepress_time = now
        end

        mousedown_time = hs.timer.secondsSinceEpoch()
        postEvent(eventTypes[btn .. "MouseDown"], coords, flags, mousepress)
      end

      orig_coords = coords
    elseif event:getType() == eventTypes.keyDown then
      local mul = 0
      local step = 20
      local x_delta = 0
      local y_delta = 0
      local scroll_y_delta = 0
      local is_tapkey = code == keycodes[tkey]

      if is_tapkey == true then
        for name, _ in pairs(tapmods) do
          if flags[name] == nil then
            flags[name] = false
          end

          if tapmods[name] ~= flags[name] then
            is_tapkey = false
            break
          end
        end
      end

      if flags.shift then
        step = 5
      end

      if flags.alt then
        mul = 5
      else
        mul = 1
      end

      if is_tapkey or code == keycodes["escape"] then
        if dragging then
          postEvent(eventTypes.leftMouseUp, coords, flags, 0)
        end
        dragging = false
        -- if overlay then
        --   overlay:delete()
        --   overlay = nil
        -- end
        hs.alert("Vi Mouse Off")
        if tap then
          tap:stop()
        end
        hs.mouse.absolutePosition(orig_coords)
        return true
      elseif (code == keycodes["j"] or code == keycodes["k"]) and flags.ctrl then
        if repeating ~= 0 then
          scrolling = scrolling + 1
        else
          scrolling = 1
        end

        local scroll_mul = 1 + math.log(scrolling)
        if code == keycodes["j"] then
          scroll_y_delta = math.ceil(-8 * scroll_mul)
        else
          scroll_y_delta = math.floor(8 * scroll_mul)
        end
        log.d("Scrolling", scrolling, "-", scroll_y_delta)
      elseif code == keycodes["h"] then
        x_delta = step * mul * -1
      elseif code == keycodes["l"] then
        x_delta = step * mul
      elseif code == keycodes["j"] then
        y_delta = step * mul
      elseif code == keycodes["k"] then
        y_delta = step * mul * -1
      end

      if scroll_y_delta ~= 0 then
        -- Use pixel-based scrolling for better compatibility
        hs.eventtap.event.newScrollEvent({ 0, scroll_y_delta }, flags, "pixel"):post()
      end

      if x_delta ~= 0 or y_delta ~= 0 then
        coords.x = coords.x + x_delta
        coords.y = coords.y + y_delta

        if dragging then
          postEvent(eventTypes.leftMouseDragged, coords, flags, 0)
        else
          hs.mouse.absolutePosition(coords)
          -- Simulate mouse movement to help Dock appear
          simulateMouseMovement(coords)
        end
        -- If at bottom edge, jiggle to trigger Dock
        local screen = hs.mouse.getCurrentScreen()
        if screen == nil then
          return true
        end
        local frame = screen:fullFrame()
        if coords.y >= (frame.y + frame.h - 2) then
          coords.y = frame.y + frame.h - 1
          hs.mouse.absolutePosition(coords)
          simulateMouseMovement(coords)
        end
      end
    end
    return true
  end)

  hs.hotkey.bind("cmd", "a", nil, function(event)
    -- local screen = hs.mouse.getCurrentScreen()
    -- if screen == nil then
    --   return
    -- end
    -- local frame = screen:fullFrame()

    -- overlay = hs.drawing.rectangle(frame)
    -- if overlay == nil then
    --   return
    -- end
    -- overlay:setFillColor({ ["red"] = 0, ["blue"] = 0, ["green"] = 0, ["alpha"] = 0.2 })
    -- overlay:setFill(true)
    -- overlay:setLevel(hs.drawing.windowLevels["assistiveTechHigh"])
    -- overlay:show()

    hs.alert("Vi Mouse On")
    orig_coords = hs.mouse.absolutePosition()
    tap:start()
  end)
end

return vimouse("cmd", "a")
