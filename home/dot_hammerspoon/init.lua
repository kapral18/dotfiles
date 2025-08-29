Hyper = { "ctrl", "alt", "cmd" }

-- spoons
hs.loadSpoon("EmmyLua")

hs.loadSpoon("RecursiveBinder")
spoon.RecursiveBinder.helperFormat.textFont = "Avenir Next Condensed"
spoon.RecursiveBinder.helperFormat.atScreenEdge = 2
spoon.RecursiveBinder.helperEntryLengthInChar = 25

-- plugins
require("keymaps")
require("launch")
-- require("gridmouse")
require("window")

-- config reload
hs.hotkey.bind(Hyper, "r", function()
  hs.reload()
end)
hs.alert.show("Config Reloaded")
