local M = {}
local tap

function M.start(callback)
  local types = hs.eventtap.event.types
  local interval = hs.eventtap.doubleClickInterval() * 1000000000
  local pressed_at, pressed_key, last_tap

  tap = hs.eventtap
    .new({
      types.flagsChanged,
      types.keyDown,
      types.leftMouseDown,
      types.rightMouseDown,
      types.otherMouseDown,
      types.scrollWheel,
    }, function(event)
      if event:getType() ~= types.flagsChanged then
        pressed_at, pressed_key, last_tap = nil, nil, nil
        return false
      end
      local flags = event:getFlags()
      local key = event:getKeyCode()
      if (key ~= 54 and key ~= 55) or flags.alt or flags.ctrl or flags.shift or flags.fn then
        pressed_at, pressed_key, last_tap = nil, nil, nil
        return false
      end
      local now = event:timestamp()
      if flags.cmd then
        if pressed_at then
          pressed_at, pressed_key, last_tap = nil, nil, nil
        else
          pressed_at, pressed_key = now, key
        end
      elseif pressed_at and pressed_key == key then
        local duration = now - pressed_at
        pressed_at, pressed_key = nil, nil
        if duration < 0 or duration > interval then
          last_tap = nil
        elseif last_tap and now - last_tap >= 0 and now - last_tap <= interval then
          last_tap = nil
          callback()
        else
          last_tap = now
        end
      else
        pressed_at, pressed_key, last_tap = nil, nil, nil
      end
      -- Observe only: normal Command shortcuts and mouse events keep propagating.
      return false
    end)
    :start()
end

return M
