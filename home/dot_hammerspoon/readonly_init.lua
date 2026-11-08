-- Load EmmyLua first for type annotations
pcall(function()
  hs.loadSpoon("EmmyLua")
end)

hs.autoLaunch(true)

Hyper = { "ctrl", "alt", "cmd" }

require("window")

local search = require("search")
require("double_command").start(search.show)

hs.hotkey.bind(Hyper, "r", function()
  hs.reload()
end)
hs.alert.show("Config Reloaded")
