local function setupKeymaps()
  if not spoon.RecursiveBinder then
    hs.alert.show("RecursiveBinder not loaded")
    return
  end

  hs.hotkey.bind(
    Hyper,
    "h",
    spoon.RecursiveBinder.recursiveBind({
      [spoon.RecursiveBinder.singleKey("c", "Console")] = hs.openConsole,
      [spoon.RecursiveBinder.singleKey("r", "Reload config")] = hs.reload,
    })
  )
end

return setupKeymaps
