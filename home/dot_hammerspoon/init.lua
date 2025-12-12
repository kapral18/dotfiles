Hyper = { "ctrl", "alt", "cmd" }

-- spoons
pcall(function() hs.loadSpoon("EmmyLua") end)

pcall(function()
  hs.loadSpoon("RecursiveBinder")
  if spoon.RecursiveBinder then
    spoon.RecursiveBinder.helperFormat.textFont = "Avenir Next Condensed"
    spoon.RecursiveBinder.helperFormat.atScreenEdge = 2
    spoon.RecursiveBinder.helperEntryLengthInChar = 25
  end
end)

-- plugins
local keymapsSetup = require("keymaps")
require("launch")
-- require("gridmouse")
require("window")

if keymapsSetup then keymapsSetup() end

-- config reload
hs.hotkey.bind(Hyper, "r", function()
  hs.reload()
end)
hs.alert.show("Config Reloaded")
