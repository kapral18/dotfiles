-- Load EmmyLua first for type annotations
pcall(function()
  hs.loadSpoon("EmmyLua")
end)

Hyper = { "ctrl", "alt", "cmd" }

-- require("gridmouse")
require("window")

-- config reload
hs.hotkey.bind(Hyper, "r", function()
  hs.reload()
end)
hs.alert.show("Config Reloaded")
