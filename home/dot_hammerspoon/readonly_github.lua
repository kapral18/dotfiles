local M =
  { title = "GitHub issues and pull requests", hint = "gh <query> — supports repo:owner/name, is:pr, is:open" }
local active = {}
local previous_shutdown = hs.shutdownCallback

hs.shutdownCallback = function()
  -- Teardown drops task callbacks; stop writers before unlinking their captures.
  for output, task in pairs(active) do
    if task:isRunning() then
      task:terminate()
      task:waitUntilExit()
    end
    os.remove(output)
    active[output] = nil
  end
  if previous_shutdown then
    previous_shutdown()
  end
end

local function executable()
  for _, path in ipairs({ "/opt/homebrew/bin/gh", "/usr/local/bin/gh", os.getenv("HOME") .. "/.local/bin/gh" }) do
    if hs.fs.attributes(path, "mode") == "file" then
      return path
    end
  end
end

function M.search(term, publish, is_current)
  local path = executable()
  if not path then
    publish({ { text = "GitHub CLI not found — install gh first", valid = false } })
    return
  end
  -- File capture preserves UTF-8 bytes and is complete when gh exits, unlike
  -- hs.task's independently decoded streaming notifications.
  local output = os.tmpname()
  local command = 'exec "$1" api --method GET search/issues -f "q=$3" -f per_page=30 > "$2" 2>/dev/null'
  local task = hs.task.new("/bin/sh", function(code)
    active[output] = nil
    local data = code == 0 and hs.json.read(output) or nil
    os.remove(output)
    if not is_current() then
      return
    end
    if type(data) ~= "table" or type(data.items) ~= "table" then
      publish({ { text = "GitHub unavailable — check gh auth status and your query", valid = false } })
      return
    end
    local choices = {}
    for _, item in ipairs(data.items) do
      local repo = item.repository_url:match("/repos/(.+)$")
      local kind = item.pull_request and "PR" or "Issue"
      choices[#choices + 1] = {
        text = item.title,
        subText = string.format("%s #%d · %s · %s", repo, item.number, kind, item.state),
        url = item.html_url,
      }
    end
    if #choices == 0 then
      choices[1] = { text = "No matching GitHub issues or pull requests", valid = false }
    end
    publish(choices)
  end, { "-c", command, "hammerspoon-github", path, output, term })
  active[output] = task
  if not task or not task:start() then
    active[output] = nil
    os.remove(output)
    publish({ { text = "Could not start GitHub CLI", valid = false } })
    return
  end
  return function()
    if task:isRunning() then
      task:terminate()
    end
  end
end

return M
