local resizeFull = function()
  local win = hs.window.focusedWindow()
  local f = win:frame()
  local screen = win:screen()
  local max = screen:frame()

  f.x = 0
  f.y = 0
  f.w = max.w
  f.h = max.h
  win:setFrame(f, 0)
end

local resizeLeft = function()
  local win = hs.window.focusedWindow()
  local f = win:frame()
  local screen = win:screen()
  local max = screen:frame()

  f.x = 0
  f.y = 0
  f.w = max.w / 2
  f.h = max.h
  win:setFrame(f, 0)
end

local resizeRight = function()
  local win = hs.window.focusedWindow()
  local f = win:frame()
  local screen = win:screen()
  local max = screen:frame()

  f.x = max.x + (max.w / 2)
  f.y = max.y
  f.w = max.w / 2
  f.h = max.h
  win:setFrame(f, 0)
end

local resizeTop = function()
  local win = hs.window.focusedWindow()
  local f = win:frame()
  local screen = win:screen()
  local max = screen:frame()

  f.x = 0
  f.y = 0
  f.w = max.w
  f.h = max.h / 2
  win:setFrame(f, 0)
end

local resizeBottom = function()
  local win = hs.window.focusedWindow()
  local f = win:frame()
  local screen = win:screen()
  local max = screen:frame()
  f.x = 0
  f.y = max.h / 2
  f.w = max.w
  f.h = max.h / 2
  win:setFrame(f, 0)
end

hs.hotkey.bind(Hyper, "h", resizeLeft)
hs.hotkey.bind(Hyper, "j", resizeBottom)
hs.hotkey.bind(Hyper, "k", resizeTop)
hs.hotkey.bind(Hyper, "l", resizeRight)
hs.hotkey.bind(Hyper, "m", resizeFull)
