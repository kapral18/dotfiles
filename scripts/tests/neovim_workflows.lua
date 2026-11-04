local root, case = arg[1], arg[2]
local base = root .. "/home/dot_config/exact_nvim/exact_lua/"
local function load_source(area, name)
  return assert(loadfile(base .. "exact_" .. area .. "/readonly_" .. name .. ".lua"))()
end
local function copy(value)
  if type(value) ~= "table" then
    return value
  end
  local result = {}
  for key, item in pairs(value) do
    result[key] = copy(item)
  end
  return result
end
local function equal(actual, expected)
  if type(actual) ~= type(expected) then
    return false
  end
  if type(actual) ~= "table" then
    return actual == expected
  end
  for key, value in pairs(actual) do
    if not equal(value, expected[key]) then
      return false
    end
  end
  for key in pairs(expected) do
    if actual[key] == nil then
      return false
    end
  end
  return true
end
local function merge(_, target, additions)
  for key, value in pairs(additions) do
    if type(target[key]) == "table" and type(value) == "table" then
      merge("force", target[key], value)
    else
      target[key] = copy(value)
    end
  end
  return target
end
local function indexed(default)
  return setmetatable({}, {
    __index = function(tbl, key)
      local value = copy(default)
      rawset(tbl, key, value)
      return value
    end,
  })
end
local current = 1
local messages = {}
vim = {
  g = {},
  b = indexed({}),
  bo = indexed({ filetype = "typescript", modifiable = true, readonly = false, modified = false, buflisted = true }),
  api = {
    nvim_get_current_buf = function()
      return current
    end,
    nvim_buf_is_valid = function(buf)
      return type(buf) == "number" and buf > 0
    end,
    nvim_buf_get_changedtick = function()
      return 1
    end,
  },
  fn = {},
  fs = {},
  lsp = { util = {} },
  log = { levels = { ERROR = 1, WARN = 2, INFO = 3 } },
  notify = function(message)
    messages[#messages + 1] = message
  end,
  inspect = tostring,
  deepcopy = copy,
  tbl_deep_extend = merge,
  tbl_isempty = function(tbl)
    return next(tbl) == nil
  end,
  tbl_contains = function(tbl, expected)
    for _, item in ipairs(tbl) do
      if item == expected then
        return true
      end
    end
    return false
  end,
  schedule = function(callback)
    callback()
  end,
  schedule_wrap = function(callback)
    return callback
  end,
}
local tests = {}

function tests.jsonl()
  local opts = load_source("plugins", "jsonl")[1].opts(nil, {})
  local formatter = opts.formatters[opts.formatters_by_ft.jsonl[1]]
  assert(formatter.stdin ~= false, "JSONL must format buffer input")
  for _, item in ipairs(formatter.args) do
    print(item)
  end
end

function tests.format()
  package.preload.snacks = function()
    return {
      toggle = function(opts)
        return opts
      end,
    }
  end
  local formatter = load_source("util", "format")
  local formatted = {}
  formatter.register({
    sources = function()
      return { "formatter" }
    end,
    format = function(buf)
      formatted[#formatted + 1] = buf
    end,
  })
  local toggle = formatter.snacks_toggle(true)
  current = 2
  toggle.set(false)
  assert(vim.b[1].autoformat == nil and vim.b[2].autoformat == false, "toggle must affect the active buffer")
  formatter.format()
  assert(#formatted == 0, "disabled buffer must retain its contents")
  current = 1
  assert(toggle.get(), "another buffer stays enabled")
  formatter.format()
  assert(equal(formatted, { 1 }))
  current = 2
  formatter.format({ force = true })
  assert(equal(formatted, { 1, 2 }), "manual force must bypass the buffer gate")
  vim.g.autoformat = false
  toggle.set(true)
  assert(not toggle.get(), "buffer enable must not override global disable")
  formatter.format({ force = true })
  assert(equal(formatted, { 1, 2, 2 }), "manual force must bypass global disable")
end

function tests.formatexpr()
  local called = false
  vim.lsp.formatexpr = function(opts)
    assert(opts.timeout_ms == 3000)
    called = true
    return 7
  end
  package.preload["util.format"] = function()
    return load_source("util", "format")
  end
  vim.opt = indexed({ append = function() end })
  vim.env, vim.o = {}, {}
  vim.fn.stdpath = function()
    return "/isolated-state"
  end
  vim.fn.mkdir = function() end
  load_source("core", "options")
  local expression = vim.opt.formatexpr:gsub("^v:lua%.", "")
  assert(
    assert((loadstring or load)("return " .. expression))() == 7 and called,
    "gq must reach the configured LSP formatexpr"
  )
end

function tests.docker()
  local names = { "/repo/compose.yaml", "/repo/settings.yaml" }
  vim.api.nvim_buf_get_name = function(buf)
    return names[buf]
  end
  vim.fn.fnamemodify = function(path, modifier)
    return modifier == ":t" and path:match("[^/]+$") or path:match("^(.*)/[^/]+$")
  end
  local specs = load_source("plugins", "docker")
  local config = specs[3].opts.servers.docker_compose_language_service
  local roots = {}
  config.root_dir(1, function(path)
    roots[#roots + 1] = path
  end)
  config.root_dir(2, function(path)
    roots[#roots + 1] = path
  end)
  assert(equal(roots, { "/repo" }), "native LSP callback must start Compose and ignore ordinary YAML")
end

function tests.terminal()
  local buffers = { [1] = true, [90] = true }
  local windows = { [1] = 1 }
  local next_buf, window, next_job = 1, 1, 100
  local stopped, deleted, callbacks, maps = {}, {}, {}, {}
  vim.bo[90].buftype, vim.bo[90].channel = "terminal", 900
  vim.api.nvim_get_current_win = function()
    return window
  end
  vim.api.nvim_set_current_win = function(win)
    assert(windows[win])
    window = win
    current = windows[win]
  end
  vim.api.nvim_buf_is_valid = function(buf)
    return buffers[buf] == true
  end
  vim.api.nvim_list_bufs = function()
    local result = {}
    for buf in pairs(buffers) do
      result[#result + 1] = buf
    end
    return result
  end
  vim.api.nvim_win_close = function(win)
    windows[win] = nil
  end
  vim.api.nvim_buf_delete = function(buf)
    assert(buf ~= 90, "user terminal was deleted")
    deleted[buf], buffers[buf] = true, nil
    if callbacks[buf] and callbacks[buf].BufWipeout then
      callbacks[buf].BufWipeout()
    end
  end
  vim.api.nvim_create_autocmd = function(event, opts)
    callbacks[opts.buffer] = callbacks[opts.buffer] or {}
    callbacks[opts.buffer][event] = opts.callback
  end
  vim.cmd = function(cmd)
    if cmd == "vsplit" then
      window = window + 1
      windows[window] = current
    end
    if cmd == "enew" then
      next_buf = next_buf + 1
      current = next_buf
      buffers[current] = true
      windows[window] = current
    end
    local deleted_buf = cmd:match("bdelete! (%d+)")
    if deleted_buf then
      vim.api.nvim_buf_delete(tonumber(deleted_buf))
    end
  end
  vim.fn.termopen = function(cmd)
    if cmd == "fail" then
      return -1
    end
    next_job = next_job + 1
    vim.bo[current].buftype, vim.bo[current].channel = "terminal", next_job
    return next_job
  end
  vim.fn.jobstop = function(job)
    assert(job ~= 900, "user job was stopped")
    stopped[job] = true
  end
  vim.empty_dict = function()
    return {}
  end
  vim.keymap = {
    set = function(_, _, callback, opts)
      maps[opts.buffer] = callback
    end,
  }
  local terminal = load_source("util", "terminal")
  assert(terminal.run_in_split("jest", { owner = "jest", focus_original = true }))
  assert(terminal.run_in_split("python", { owner = "python", focus_original = true, close_on_exit = true }))
  assert(not stopped[101] and buffers[90], "other owners must keep running")
  assert(terminal.run_in_split("jest again", { owner = "jest", focus_original = true }))
  assert(stopped[101] and deleted[2] and not stopped[102])
  assert(not terminal.run_in_split("fail", { owner = "jest", focus_original = true }))
  assert(not stopped[103], "failed replacement must preserve the previous job")
  terminal.close("jest")
  assert(stopped[103] and not stopped[102] and buffers[90])
  callbacks[3].TermClose()
  assert(stopped[102] and deleted[3] and buffers[90])
  if arg[3] then
    package.preload["util.terminal"] = function()
      return terminal
    end
    local jobs = {}
    for command in io.lines(arg[3]) do
      assert(command:sub(1, 4) == "lua ", "batch caller must emit an editor Lua command")
      assert((loadstring or load)(command:sub(5)))()
      jobs[#jobs + 1] = next_job
    end
    assert(#jobs == 2 and jobs[1] ~= jobs[2], "each batch must launch its own helper")
    assert(not stopped[jobs[1]] and not stopped[jobs[2]], "another batch must not replace an in-flight helper")
    assert(buffers[90], "batch helper must preserve user terminals")
  end
end

function tests.k8s()
  local pending, fetched = {}, {}
  vim.system = function(args, _, callback)
    fetched[#fetched + 1] = args[3]
    pending[#pending + 1] = { url = args[3], callback = callback }
  end
  vim.json = {
    decode = function(value)
      return assert(({
        old = { version = "old" },
        new = { version = "new" },
        fallback = { properties = { spec = { ["$ref"] = "io.k8s.api.Spec" } } },
        child = { type = "object" },
      })[value])
    end,
  }
  local k8s = load_source("util", "k8s")
  local version = "https://schema/old/"
  k8s.get_base_url = function()
    return version
  end
  k8s.get_default_version = function()
    return "v1.30.0"
  end
  local old, new
  k8s.fetch_schema("pod-v1.json", function(schema)
    old = schema.version
  end)
  pending[1].callback({ code = 0, stdout = "old" })
  version = "https://schema/new/"
  k8s.fetch_schema("pod-v1.json", function(schema)
    new = schema.version
  end)
  assert(#fetched == 2, "the same resource in another Kubernetes version must fetch independently")
  pending[2].callback({ code = 0, stdout = "new" })
  assert(old == "old" and new == "new")
  version = "https://schema/old/"
  k8s.fetch_schema("pod-v1.json", function(schema)
    assert(schema.version == "old")
  end)
  assert(#fetched == 2, "same-version cache should still be reused")
  k8s.fetch_schema("deployment-v1.json", function(schema, resolved)
    k8s.navigate_schema(schema, { "spec" }, function(result)
      assert(result.type == "object")
    end, 1, schema, resolved)
  end)
  pending[3].callback({ code = 22, stdout = "" })
  version = "https://schema/another-chart/"
  pending[4].callback({ code = 0, stdout = "fallback" })
  assert(
    fetched[5]
      == "https://raw.githubusercontent.com/yannh/kubernetes-json-schema/master/v1.30.0-standalone-strict/spec-v1.json",
    "async references must stay on the successfully resolved version"
  )
  pending[5].callback({ code = 0, stdout = "child" })
end

function tests.python_commands()
  local file = assert(arg[3])
  local has_pytest = true
  package.preload["util.fs"] = function()
    return load_source("util", "fs")
  end
  package.preload["util.terminal"] = function()
    return {
      run_in_split = function(command, opts)
        assert(opts.owner == "python")
        print(command)
      end,
    }
  end
  vim.fn.expand = function()
    return file
  end
  vim.fn.executable = function(name)
    return name == "pytest" and has_pytest and 1 or 0
  end
  local class = {
    type = function()
      return "class_definition"
    end,
    field = function()
      return { { text = "TestWidget" } }
    end,
    parent = function()
      return nil
    end,
  }
  local test_function = {
    type = function()
      return "function_definition"
    end,
    field = function()
      return { { text = "test_value" } }
    end,
    parent = function()
      return class
    end,
  }
  vim.treesitter = {
    get_node = function()
      return test_function
    end,
    get_node_text = function(node)
      return node.text
    end,
  }
  local run
  for _, spec in ipairs(load_source("plugins", "python")) do
    for _, key in ipairs(spec.keys or {}) do
      if key[1] == "<leader>tt" then
        run = key[2]
      end
    end
  end
  assert(run, "Python test callback must remain registered")
  run()
  has_pytest = false
  run()
  file, test_function = assert(arg[4]), nil
  run()
end

function tests.jest()
  local test = "/project/packages/widget/example's space.test.ts"
  local script = "jest"
  local files = {
    ["/project/packages/widget/package.json"] = true,
    ["/project/pnpm-lock.yaml"] = true,
    ["/project/node_modules/.bin/jest"] = true,
    ["/project/jest.config.js"] = true,
    ["/cache/run-jest-in-split/jest-config-choices.json"] = true,
  }
  package.preload["util.fs"] = function()
    return {
      file_exists = function(path)
        return files[path] == true
      end,
      get_project_root = function()
        return "/project"
      end,
      safe_file_read = function()
        return "cache"
      end,
      escape_shell_arg = load_source("util", "fs").escape_shell_arg,
    }
  end
  package.preload["util.terminal"] = function()
    return {
      run_in_split = function(cmd, opts)
        print(cmd)
        print(opts.cwd)
      end,
    }
  end
  vim.env, vim.v = {}, { shell_error = 0 }
  vim.fs.normalize = function(path)
    return path:gsub("/+$", "")
  end
  vim.fs.joinpath = function(...)
    return table.concat({ ... }, "/")
  end
  vim.fn.fnamemodify = function(path, modifier)
    if modifier == ":p:h" or modifier == ":h" then
      return path:match("^(.*)/[^/]+$") or "/"
    end
    return path
  end
  vim.fn.readfile = function()
    return { "package" }
  end
  vim.fn.json_decode = function(value)
    if value == "package" then
      return { scripts = { test = script } }
    end
    return { ["/project|main|" .. test] = "/project/jest.config.js" }
  end
  vim.fn.systemlist = function()
    return { "main" }
  end
  vim.fn.stdpath = function()
    return "/cache"
  end
  vim.fn.isdirectory = function()
    return 1
  end
  vim.fn.expand = function()
    return test
  end
  local jest = load_source("plugins_local_src", "run-jest-in-split")
  jest.run_jest_cmd("", true)
  script = "node ./run-jest.js"
  jest.run_jest_cmd("", true)
  jest.run_jest_cmd("", false)
end

local function move_case(failure)
  local buffers = {
    [1] = {
      path = "/project/source.ts",
      lines = {
        "import { dependency } from './dependency';",
        "export const moved = dependency;",
        "export const stay = 2;",
      },
      tick = 1,
    },
    [2] = { path = "/project/target.ts", lines = { "export const existing = 3;" }, tick = 1, loaded = false },
    [3] = { path = "/project/importer.ts", lines = { "import { moved, stay } from './source';" }, tick = 1 },
  }
  local originals = copy(buffers)
  local disk = {}
  for _, buffer in pairs(buffers) do
    disk[buffer.path] = copy(buffer.lines)
  end
  local original_disk = copy(disk)
  local function replacement(text, line_count)
    return {
      {
        range = { start = { line = 0, character = 0 }, ["end"] = { line = line_count, character = 0 } },
        newText = text,
      },
    }
  end
  local edits = {
    changes = {
      ["file:///project/source.ts"] = replacement("export const stay = 2;", 3),
      ["file:///project/target.ts"] = replacement(
        "import { dependency } from './dependency';\nexport const existing = 3;\nexport const moved = dependency;",
        1
      ),
      ["file:///project/importer.ts"] = replacement(
        "import { stay } from './source';\nimport { moved } from './target';",
        1
      ),
    },
  }
  local requests, mode, applied = {}, "success", false
  local client = { offset_encoding = "utf-16" }
  function client:request_sync(method, params)
    requests[#requests + 1] = method
    if method == "textDocument/references" then
      return { result = { { uri = "file:///project/importer.ts" } } }
    end
    if method == "textDocument/rename" then
      local old_name = assert(buffers[current].lines[params.position.line + 1]:match("export const ([%w_]+)"))
      local changes = {}
      for _, buffer in pairs(buffers) do
        local lines, changed = {}, false
        for _, line in ipairs(buffer.lines) do
          local rewritten, count = line:gsub("%f[%w_]" .. old_name .. "%f[^%w_]", params.newName)
          lines[#lines + 1], changed = rewritten, changed or count > 0
        end
        if changed then
          changes["file://" .. buffer.path] = replacement(table.concat(lines, "\n"), #buffer.lines)
        end
      end
      return { result = { changes = changes } }
    end
    if method == "textDocument/codeAction" then
      assert(params.range.start.line == 1 and params.range["end"].line == 1)
      return {
        result = {
          { data = { action = "Move to file", refactor = "Move to file" }, command = { command = "interactive" } },
        },
      }
    end
    assert(
      method == "codeAction/resolve" and params.command == nil,
      "resolve must reach tsserver rather than interactive command short-circuit"
    )
    assert(params.data.interactiveRefactorArguments.targetFile == "/project/target.ts")
    if mode == "resolve_error" then
      return { err = "unavailable" }
    end
    if mode == "changed" then
      buffers[3].tick = 2
    end
    return { result = { edit = edits } }
  end
  vim.lsp.get_clients = function()
    return { client }
  end
  vim.lsp.util.make_text_document_params = function()
    return { uri = "file:///project/source.ts" }
  end
  vim.lsp.util.apply_workspace_edit = function(edit, encoding)
    assert(encoding == "utf-16")
    applied = true
    local applied_count = 0
    for uri, changes in pairs(edit.changes) do
      local buf = vim.uri_to_bufnr(uri)
      for _, change in ipairs(changes) do
        local range = change.range
        assert(range.start.line == 0 and range.start.character == 0 and range["end"].line == #buffers[buf].lines)
        local lines = {}
        for line in (change.newText .. "\n"):gmatch("(.-)\n") do
          lines[#lines + 1] = line
        end
        buffers[buf].lines = lines
        vim.bo[buf].modified = true
      end
      applied_count = applied_count + 1
      if mode == "partial" and applied_count == 1 then
        error("cannot apply another file edit")
      end
    end
  end
  vim.api.nvim_buf_get_name = function(buf)
    return buffers[buf].path
  end
  vim.api.nvim_buf_get_mark = function()
    return { 2, 0 }
  end
  vim.api.nvim_list_bufs = function()
    return { 1, 2, 3 }
  end
  vim.api.nvim_buf_is_loaded = function(buf)
    return buffers[buf].loaded ~= false
  end
  vim.api.nvim_buf_get_changedtick = function(buf)
    return buffers[buf].tick
  end
  vim.api.nvim_buf_get_lines = function(buf, first, last)
    local result = {}
    if last < 0 then
      last = #buffers[buf].lines
    end
    for index = first + 1, last do
      result[#result + 1] = buffers[buf].lines[index]
    end
    return result
  end
  vim.api.nvim_buf_set_lines = function(buf, first, last, _, lines)
    if last < 0 then
      last = #buffers[buf].lines
    end
    local updated = {}
    for index = 1, first do
      updated[#updated + 1] = buffers[buf].lines[index]
    end
    for _, line in ipairs(lines) do
      updated[#updated + 1] = line
    end
    for index = last + 1, #buffers[buf].lines do
      updated[#updated + 1] = buffers[buf].lines[index]
    end
    buffers[buf].lines, vim.bo[buf].modified = updated, true
  end
  vim.fn.bufload = function(buf)
    if buffers[buf].loaded == false then
      buffers[buf].lines, buffers[buf].loaded = copy(disk[buffers[buf].path] or {}), true
    end
  end
  vim.uri_to_bufnr = function(uri)
    for buf, state in pairs(buffers) do
      if uri == "file://" .. state.path then
        return buf
      end
    end
    error("unexpected buffer")
  end
  vim.uri_to_fname = function(uri)
    return uri:gsub("^file://", "")
  end
  vim.str_utfindex = function(text)
    return #text
  end
  vim.fs.dirname = function(path)
    return path:match("^(.*)/[^/]+$")
  end
  vim.fs.joinpath = function(...)
    return table.concat({ ... }, "/")
  end
  vim.fs.normalize = function(path)
    return path
  end
  vim.ui = {
    input = function(_, callback)
      callback("target.ts")
    end,
  }
  vim.api.nvim_get_current_win = function()
    return 1
  end
  vim.api.nvim_set_current_win = function() end
  vim.api.nvim_win_is_valid = function()
    return true
  end
  vim.api.nvim_win_set_buf = function(_, buf)
    current = buf
  end
  vim.api.nvim_buf_line_count = function(buf)
    return #buffers[buf].lines
  end
  vim.api.nvim_buf_call = function(buf, callback)
    local previous = current
    current = buf
    callback()
    current = previous
  end
  vim.fn.expand = function()
    return "/project"
  end
  vim.fn.mkdir = function() end
  vim.fn.filereadable = function(path)
    return disk[path] and 1 or 0
  end
  vim.fn.readfile = function(path)
    return copy(assert(disk[path]))
  end
  vim.fn.writefile = function(lines, path)
    disk[path] = copy(lines)
    return 0
  end
  vim.fn.bufadd = function(path)
    return vim.uri_to_bufnr("file://" .. path)
  end
  vim.fn.fnamemodify = function(path)
    return path
  end
  vim.list_extend = function(target, lines)
    for _, line in ipairs(lines) do
      target[#target + 1] = line
    end
    return target
  end
  vim.tbl_keys = function(tbl)
    local keys = {}
    for key in pairs(tbl) do
      keys[#keys + 1] = key
    end
    return keys
  end
  vim.cmd = function(command)
    assert(command == "write")
    disk[buffers[current].path], vim.bo[current].modified = copy(buffers[current].lines), false
  end
  local clock = 0
  vim.loop = {
    now = function()
      clock = clock + 4000
      return clock
    end,
  }
  vim.wait = function() end
  vim.diagnostic = {
    get = function()
      return { { code = 2305 } }
    end,
  }
  package.preload["typescript-tools.api"] = function()
    -- The installed API handles 2304/2552; this fixture's existing import reports 2305.
    return { add_missing_imports = function() end }
  end
  vim.treesitter = {
    get_parser = function()
      return {
        parse = function()
          return { {
            root = function()
              return {}
            end,
          } }
        end,
      }
    end,
    get_node_text = function(node)
      return node.name
    end,
    query = {
      parse = function()
        return {
          captures = { "export_name" },
          iter_captures = function(_, _, buf, first, last)
            local nodes = {}
            for index, line in ipairs(buffers[buf].lines) do
              local name = line:match("^export const ([%w_]+)")
              if name and index - 1 >= first and index - 1 < last then
                nodes[#nodes + 1] = {
                  name = name,
                  start = function()
                    return index - 1, 13
                  end,
                }
              end
            end
            local index = 0
            return function()
              index = index + 1
              if nodes[index] then
                return 1, nodes[index]
              end
            end
          end,
        }
      end,
    },
  }
  local mover = load_source("plugins_local_src", "ts-move-exports")
  if not failure then
    mover.ts_move_exports()
    assert(
      applied and buffers[3].lines[2] == "import { moved } from './target';",
      "moved imports must point to the target module"
    )
    assert(equal(disk, original_disk), "refactor must leave the complete workspace unsaved for review")
    assert(equal(requests, { "textDocument/codeAction", "codeAction/resolve" }))
    assert(
      buffers[2].lines[2] == "export const existing = 3;"
        and buffers[2].lines[3] == "export const moved = dependency;"
        and vim.bo[2].modified
    )
    return
  end
  for _, scenario in ipairs({ "resolve_error", "partial", "changed", "dirty_target" }) do
    buffers, requests, applied, mode = copy(originals), {}, false, scenario
    disk, current = copy(original_disk), 1
    for buf in pairs(buffers) do
      vim.bo[buf].modified = false
    end
    if scenario == "dirty_target" then
      vim.bo[2].modified, buffers[2].loaded = true, true
    end
    mover.ts_move_exports()
    for buf in pairs(buffers) do
      assert(equal(buffers[buf].lines, originals[buf].lines), scenario .. " lost buffer content")
    end
    if scenario == "partial" then
      assert(applied, "the fixture must exercise partial application")
      for buf in pairs(buffers) do
        assert(not vim.bo[buf].modified, "partial application must restore modified flags")
      end
    else
      assert(not applied, scenario .. " must not apply edits")
    end
  end
end
function tests.move()
  move_case(false)
end
function tests.move_failure()
  move_case(true)
end

assert(tests[case], "unknown workflow case")()
