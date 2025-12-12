Hyper = { "ctrl", "alt", "cmd" }

-- spoons
pcall(function() hs.loadSpoon("EmmyLua") end)

-- require("gridmouse")
require("window")

-- config reload
hs.hotkey.bind(Hyper, "r", function()
  hs.reload()
end)
hs.alert.show("Config Reloaded")
