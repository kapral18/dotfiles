local function appLaunchFn(name)
  return function()
    hs.application.launchOrFocus(name)
  end
end

hs.hotkey.bind(
  Hyper,
  "b",
  spoon.RecursiveBinder.recursiveBind({
    [spoon.RecursiveBinder.singleKey("5", "Arc")] = appLaunchFn("Arc"),
    [spoon.RecursiveBinder.singleKey("6", "Ghostty")] = appLaunchFn("Ghostty"),
    [spoon.RecursiveBinder.singleKey("7", "Slack")] = appLaunchFn("Slack"),
    [spoon.RecursiveBinder.singleKey("8", "Telegram")] = appLaunchFn("Telegram"),
  })
)
