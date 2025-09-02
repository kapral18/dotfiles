hs.hotkey.bind(
  Hyper,
  "h",
  spoon.RecursiveBinder.recursiveBind({
    [spoon.RecursiveBinder.singleKey("c", "Console")] = hs.openConsole,
    [spoon.RecursiveBinder.singleKey("r", "Reload config")] = hs.reload,
  })
)
