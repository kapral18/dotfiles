local resizeFull = function()
  local win = hs.window.focusedWindow()
  if not win then return end
  local screen = win:screen()
  local max = screen:frame()

  win:setFrame(hs.geometry(0, 0, max.w, max.h))
end

local resizeLeft = function()
  local win = hs.window.focusedWindow()
  if not win then return end
  local screen = win:screen()
  local max = screen:frame()

  win:setFrame(hs.geometry(0, 0, max.w / 2, max.h))
end

local resizeRight = function()
  local win = hs.window.focusedWindow()
  if not win then return end
  local screen = win:screen()
  local max = screen:frame()

  win:setFrame(hs.geometry(max.x + (max.w / 2), max.y, max.w / 2, max.h))
end

local resizeTop = function()
  local win = hs.window.focusedWindow()
  if not win then return end
  local screen = win:screen()
  local max = screen:frame()

  win:setFrame(hs.geometry(0, 0, max.w, max.h / 2))
end

local resizeBottom = function()
  local win = hs.window.focusedWindow()
  if not win then return end
  local screen = win:screen()
  local max = screen:frame()
  win:setFrame(hs.geometry(0, max.h / 2, max.w, max.h / 2))
end

hs.hotkey.bind(Hyper, "h", resizeLeft)
hs.hotkey.bind(Hyper, "j", resizeBottom)
hs.hotkey.bind(Hyper, "k", resizeTop)
hs.hotkey.bind(Hyper, "l", resizeRight)
hs.hotkey.bind(Hyper, "m", resizeFull)
