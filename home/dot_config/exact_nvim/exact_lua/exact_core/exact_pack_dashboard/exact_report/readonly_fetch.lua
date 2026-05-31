local notify = require("core.pack_dashboard.report.notify")

local M = {}

local function fetch_pack_remotes_async(names, callback, progress_callback)
  local function report_progress(done_count, total_count)
    if type(progress_callback) ~= "function" then
      return
    end
    vim.schedule(function()
      progress_callback({
        done = done_count,
        total = total_count,
      })
    end)
  end

  local ok, plugins = pcall(vim.pack.get, names, { info = false })
  if not ok or type(plugins) ~= "table" then
    notify.notify_err("Failed to read vim.pack plugins")
    vim.schedule(function()
      callback({})
    end)
    return
  end

  local targets = {}
  for _, plugin in ipairs(plugins) do
    local name = plugin and plugin.spec and plugin.spec.name
    local path = plugin and plugin.path
    if type(name) == "string" and name ~= "" and type(path) == "string" and path ~= "" then
      targets[#targets + 1] = { name = name, path = path }
    end
  end

  if #targets == 0 then
    vim.schedule(function()
      callback({})
    end)
    return
  end

  local env = vim.fn.environ()
  env.GIT_DIR = nil
  env.GIT_WORK_TREE = nil
  local max_jobs = tonumber(vim.g.pack_dashboard_fetch_concurrency) or 8
  max_jobs = math.max(1, math.min(#targets, max_jobs))

  local errors = {}
  local next_index = 1
  local running = 0
  local done = 0
  local finished = false
  report_progress(0, #targets)

  local function finish_if_done()
    if finished or done < #targets then
      return
    end
    finished = true
    vim.schedule(function()
      callback(errors)
    end)
  end

  local function launch_next()
    while running < max_jobs and next_index <= #targets do
      local target = targets[next_index]
      next_index = next_index + 1
      running = running + 1
      vim.system({
        "git",
        "-c",
        "gc.auto=0",
        "fetch",
        "--quiet",
        "--tags",
        "--force",
        "--recurse-submodules=yes",
        "origin",
      }, {
        cwd = target.path,
        text = true,
        env = env,
        clear_env = true,
      }, function(out)
        running = running - 1
        done = done + 1
        report_progress(done, #targets)
        if out.code ~= 0 then
          errors[target.name] = vim.trim(out.stderr or out.stdout or "git fetch failed")
        end
        vim.schedule(launch_next)
        finish_if_done()
      end)
    end
    finish_if_done()
  end

  launch_next()
end

M.fetch_pack_remotes_async = fetch_pack_remotes_async

return M
