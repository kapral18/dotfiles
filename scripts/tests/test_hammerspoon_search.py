from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
MODULE = REPO / "home/dot_hammerspoon/readonly_search.lua"
PROVIDER = REPO / "home/dot_hammerspoon/readonly_urban_dictionary.lua"
GESTURE = REPO / "home/dot_hammerspoon/readonly_double_command.lua"


# Resolve mise installations from the shim's path without executing the shim:
# test shards deliberately replace HOME and must not consult user configuration.
def lua_interpreter() -> str | None:
    concrete = shutil.which(
        "lua", path=os.pathsep.join(path for path in os.get_exec_path() if Path(path).name != "shims")
    )
    if concrete:
        return concrete
    shim = shutil.which("lua")
    if shim and Path(shim).resolve().name == "mise":
        installed = sorted((Path(shim).parent.parent / "installs/lua").glob("*/bin/lua"), reverse=True)
        return next((str(path) for path in installed if os.access(path, os.X_OK)), None)
    return None


LUA = lua_interpreter()

# Only the Hammerspoon UI, timer and network boundaries are replaced. The real
# module handles query parsing, ranking, state invalidation and selection.
HARNESS = r"""
local requests, timers, opened, tasks, copied, launched, posts, panel_taps = {}, {}, {}, {}, {}, {}, {}, {}
local alerts, task_failure = {}, nil
local files = {
  ['/Applications'] = { mode = 'directory', entries = { 'Safari.app', 'Safari Technology Preview.app', 'Utilities' } },
  ['/Applications/Safari.app'] = { mode = 'directory' },
  ['/Applications/Safari Technology Preview.app'] = { mode = 'directory' },
  ['/Applications/Utilities'] = { mode = 'directory', entries = { 'Café.app' } },
  ['/Applications/Utilities/Café.app'] = { mode = 'directory' },
  ['/opt/homebrew/bin/gh'] = { mode = 'file' },
}
local event_callback
local chooser = { visible = false, items = {} }
local function copy(value)
  if type(value) ~= 'table' then return value end
  local result = {}
  for key, item in pairs(value) do result[key] = copy(item) end
  return result
end
-- Native choices reload selects the first row; selectedRow(n) clamps to the list.
function chooser:choices(items) self.items = copy(items); self.row = 1; return self end
function chooser:selectedRow(row)
  if row == nil then return self.row or 1 end
  self.row = math.max(1, math.min(row, #self.items))
  return self
end
function chooser:query(value) self.queryText = value; return self end
function chooser:show() self.visible = true; self.hasChosen = false; self.changed(self.queryText); return self end
function chooser:hide() self.visible = false; self.hidden(); return self end
function chooser:isVisible() return self.visible end
function chooser:queryChangedCallback(fn) self.changed = fn; return self end
function chooser:hideCallback(fn) self.hidden = fn; return self end
function chooser:invalidCallback(fn) self.invalid = fn; return self end
function chooser:select(index)
  local choice = self.items[index]
  self.hasChosen = true
  if choice.valid == false and self.invalid then self.invalid(choice); return end
  self:hide()
  self.completed(choice)
end
function chooser:escape()
  if not self.hasChosen then self:hide(); self.completed(nil) end
end
-- Native hs.chooser:cancel hides (running hideCallback) and then completes with nil.
function chooser:cancel() self:hide(); self.completed(nil); return self end
function chooser:placeholderText(text) return self end
function chooser:rows(rows) return self end
function chooser:width(width) return self end
local payloads = {}
local filePayloads = {}
local encodedInput
local tempSequence = 0
os.tmpname = function()
  tempSequence = tempSequence + 1
  local path = arg[4] .. '/capture-' .. tempSequence
  local file = assert(io.open(path, 'w'))
  file:close()
  return path
end
hs = {
  chooser = { new = function(fn) chooser.completed = fn; return chooser end },
  eventtap = {
    keyStroke = function() end,
    doubleClickInterval = function() return 0.4 end,
    event = { types = { flagsChanged = 1, keyDown = 2, leftMouseDown = 3, rightMouseDown = 4, otherMouseDown = 5, scrollWheel = 6 } },
    new = function(types, fn)
      local tap = { fn = fn, running = false }
      function tap:start() self.running = true; return self end
      function tap:stop() self.running = false; return self end
      -- The double-Command gesture watches modifier changes; the panel tap watches keyDown only.
      if types[1] == 1 then event_callback = fn else panel_taps[#panel_taps + 1] = tap end
      return tap
    end,
  },
  timer = { doAfter = function(_, fn)
    local timer = { callback = fn, stop = function(self) self.stopped = true end }
    timers[#timers + 1] = timer
    return timer
  end },
  http = {
    asyncGet = function(url, _, fn)
      requests[#requests + 1] = { url = url, callback = fn }
    end,
    asyncPost = function(url, body, headers, fn)
      posts[#posts + 1] = { url = url, body = body, headers = headers, callback = fn }
    end,
  },
  json = {
    decode = function(body)
      if not payloads[body] then error('invalid JSON') end
      return payloads[body]
    end,
    read = function(path) return filePayloads[path] end,
    encode = function(value)
      if value.messages then
        local body = 'chat:' .. (#posts + 1)
        payloads[body] = value
        return body
      end
      encodedInput = value
      local strings = {}
      for _, text in ipairs(value) do strings[#strings + 1] = string.format('%q', text) end
      return '[' .. table.concat(strings, ',') .. ']'
    end,
  },
  -- Input-dependent native folding for fixture accents; real Foundation is
  -- exercised separately by the disposable native smoke, without touching apps.
  osascript = { javascript = function()
    local accents = { ['é'] = 'e', ['É'] = 'e', ['Å'] = 'a', ['å'] = 'a', ['Ñ'] = 'n', ['ñ'] = 'n', ['µ'] = 'μ', ['Π'] = 'π', ['́'] = '' }
    local normalized = {}
    for index, text in ipairs(encodedInput) do
      normalized[index] = text:lower():gsub('[\128-\255]+', function(character)
        return accents[character] or character
      end)
    end
    payloads.folded = normalized
    return true, 'folded'
  end },
  urlevent = { openURL = function(url) opened[#opened + 1] = url; return true end },
  configdir = tostring(arg[1]):match('^(.*)/[^/]+$'),
  fs = {
    attributes = function(path, key) return files[path] and files[path][key] end,
    pathToAbsolute = function(path) return files[path] and (files[path].target or path) end,
    dir = function(path)
      local index = 0
      return function()
        index = index + 1
        return files[path].entries[index]
      end
    end,
  },
  pasteboard = { setContents = function(text) copied[#copied + 1] = text; return true end },
  application = { launchOrFocus = function(path) launched[#launched + 1] = path; return true end },
  alert = { show = function(text) alerts[#alerts + 1] = text end },
  task = { new = function(path, callback, stream, arguments)
    if type(stream) == 'table' then arguments, stream = stream, nil end
    if task_failure == 'new' then return nil end
    local task = { path = path, callback = callback, stream = stream, arguments = arguments, running = false, inputs = {} }
    function task:start()
      if task_failure == 'start' then return false end
      self.running = true
      if self.path == '/usr/bin/open' then
        if self.arguments[1] == '-a' then launched[#launched + 1] = self.arguments[2]
        else opened[#opened + 1] = self.arguments[2] end
      end
      return self
    end
    function task:isRunning() return self.running end
    function task:terminate()
      self.running = false
      self.terminated = true
      if self.callback then self.callback(15, '', '') end
    end
    function task:waitUntilExit() self.running = false; return self end
    function task:setInput(value) self.inputs[#self.inputs + 1] = value; return self end
    tasks[#tasks + 1] = task
    return task
  end },
}
package.preload.urban_dictionary = function() return dofile(arg[2]) end
package.path = tostring(arg[1]):match('^(.*)/[^/]+$') .. '/readonly_?.lua;' .. package.path
local app = dofile(arg[1])
dofile(arg[3]).start(app.show)
local function emit(kind, key, flags, seconds)
  local event = {
    getType = function() return kind end,
    getKeyCode = function() return key end,
    getFlags = function() return flags end,
    timestamp = function() return seconds * 1000000000 end,
  }
  assert(event_callback(event) == false, 'normal input event was consumed')
end
local function typeQuery(query)
  chooser.queryText = query
  chooser.changed(query)
end
local function tick()
  local timer = timers[#timers]
  if timer and not timer.stopped then timer.callback() end
end
local function respond(index, payload, status)
  local body = tostring(index) .. ':' .. tostring(payload)
  payloads[body] = payload
  requests[index].callback(status or 200, body)
end
local function finishTask(index, payload, status)
  filePayloads[tasks[index].arguments[5]] = payload
  tasks[index].running = false
  tasks[index].callback(status or 0, '', '')
end
local function passReply(index, code, stdout)
  tasks[index].running = false
  tasks[index].callback(code, stdout, '')
end
local function chatRequest(index)
  return payloads[posts[index].body]
end
local function chatReply(index, status, data)
  local body = 'chat-reply:' .. index
  payloads[body] = data
  posts[index].callback(status, body)
end
local function answer(text, transliteration)
  local body = 'translation:' .. tostring(text)
  payloads[body] = { translation = text, transliteration = transliteration or text }
  return { choices = { { message = { content = body } } } }
end
local function findChoice(key, value)
  for _, choice in ipairs(chooser.items) do
    if choice[key] == value then return choice end
  end
  error('missing choice: ' .. value)
end
local function shutdown()
  if hs.shutdownCallback then hs.shutdownCallback() end
end
local function equal(actual, expected)
  assert(actual == expected, 'expected ' .. tostring(expected) .. ', got ' .. tostring(actual))
end
-- Physical ANSI key codes, so bindings follow key position under any input layout.
local KEYCODES = { escape = 53, c = 8, j = 38, k = 40, n = 45, p = 35, down = 125, up = 126, a = 0 }
-- Sends one keyDown through running panel taps; returns whether a tap consumed it.
local function press(mods, key)
  local flags = {}
  for mod in mods:gmatch('[^+]+') do flags[mod] = true end
  local event = { getKeyCode = function() return KEYCODES[key] end, getFlags = function() return flags end }
  for _, tap in ipairs(panel_taps) do
    if tap.running and tap.fn(event) then return true end
  end
  return false
end
"""

DISMISS_KEYS = {"Escape": ("", "escape"), "Ctrl-C": ("ctrl", "c")}
NAVIGATION_KEYS = {
    "Ctrl-J": (("ctrl", "j"), 1),
    "Ctrl-K": (("ctrl", "k"), -1),
    "Down": (("", "down"), 1),
    "Up": (("", "up"), -1),
    "Ctrl-N": (("ctrl", "n"), 1),
    "Ctrl-P": (("ctrl", "p"), -1),
}


class TestHammerspoonSearch(unittest.TestCase):
    """WHEN the live chooser receives asynchronous search responses."""

    def run_lua(self, scenario: str):
        self.assertIsNotNone(LUA, "An installed Lua interpreter must be discoverable on PATH or beside its mise shim")
        with tempfile.TemporaryDirectory(prefix="hammerspoon-search-") as scratch:
            result = subprocess.run(
                [LUA, "-", str(MODULE), str(PROVIDER), str(GESTURE), scratch],
                input=HARNESS + scenario,
                check=False,
                capture_output=True,
                text=True,
                cwd=REPO,
                timeout=10,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_should_release_the_chooser_while_the_selected_app_is_still_starting(self):
        self.run_lua(r"""
app.show()
typeQuery('Safari')
chooser:select(1)
equal(chooser.visible, false)
equal(#tasks, 1)
equal(tasks[1].path, '/usr/bin/open')
equal(tasks[1].arguments[1], '-a')
equal(tasks[1].arguments[2], '/Applications/Safari.app')
equal(tasks[1].running, true)
app.show()
assert(press('ctrl', 'j'))
equal(chooser:selectedRow(), 2)
equal(tasks[1].running, true)
""")

    def test_should_show_the_translations_latin_reading_below_its_native_script(self):
        self.run_lua(r"""
app.show()
typeQuery('tr ja Hello'); tick()
passReply(1, 0, 'sk-test\n')
chatReply(1, 200, answer('こんにちは', 'Konnichiwa'))
equal(chooser.items[1].text, 'こんにちは')
assert(chooser.items[1].subText:find('Konnichiwa', 1, true), chooser.items[1].subText)
chooser:select(1)
equal(copied[1], 'こんにちは')
""")

    def test_should_report_app_dispatch_failures_without_replacing_a_reopened_panel(self):
        for failure in ("new", "start", "exit"):
            with self.subTest(failure=failure):
                self.run_lua(f"""
app.show()
typeQuery('Safari')
task_failure = '{failure}'
chooser:select(1)
app.show()
typeQuery('Café')
{'passReply(1, 1, "")' if failure == "exit" else ""}
equal(alerts[1], 'Application unavailable — reopen the panel to refresh')
equal(chooser.items[1].text, 'Café')
""")

    def test_should_keep_repeated_app_launches_independent_of_new_searches(self):
        self.run_lua(r"""
app.show()
typeQuery('Safari'); chooser:select(1)
app.show()
typeQuery('Safari'); chooser:select(1)
equal(tasks[1].running, true)
equal(tasks[2].running, true)
passReply(2, 0, '')
equal(tasks[1].running, true)
passReply(1, 0, '')
equal(#launched, 2)
equal(#alerts, 0)
""")

    def test_should_stop_pending_launchers_silently_on_shutdown(self):
        self.run_lua(r"""
app.show()
typeQuery('Safari'); chooser:select(1)
shutdown()
equal(tasks[1].terminated, true)
equal(#alerts, 0)
""")

    def test_should_open_a_result_url_literally_without_waiting_for_the_browser(self):
        self.run_lua(r"""
app.show()
typeQuery('ud café & tea'); tick()
respond(1, { 'café & tea' })
chooser:select(1)
equal(chooser.visible, false)
equal(tasks[1].path, '/usr/bin/open')
equal(tasks[1].arguments[1], '-u')
equal(tasks[1].arguments[2], 'https://www.urbandictionary.com/define.php?term=caf%C3%A9%20%26%20tea')
equal(#tasks[1].arguments, 2)
equal(tasks[1].running, true)
passReply(1, 1, '')
equal(alerts[1], 'Could not open the selected URL')
""")

    def test_should_reject_missing_or_malformed_translation_fields(self):
        for fields in (
            "nil",
            "'plain text'",
            "{ translation = 'Привет' }",
            "{ translation = 'Привет', transliteration = 12 }",
            "{ translation = 'Привет', transliteration = '  ' }",
            "{ translation = {}, transliteration = 'Privet' }",
            "{ translation = '  ', transliteration = 'Privet' }",
        ):
            with self.subTest(fields=fields):
                self.run_lua(f"""
app.show()
typeQuery('tr ru Hello'); tick()
passReply(1, 0, 'sk-test\\n')
payloads.invalid_translation = {fields}
chatReply(1, 200, {{ choices = {{ {{ message = {{ content = 'invalid_translation' }} }} }} }})
equal(chooser.items[1].valid, false)
chooser:select(1)
equal(#copied, 0)
""")

    def test_should_read_the_key_once_and_copy_the_newest_translation(self):
        self.run_lua(r"""
app.show()
typeQuery('tr ru Hello'); tick()
equal(#tasks, 1)
passReply(1, 0, 'sk-test\n')
local first = chatRequest(1)
equal(first.messages[2].content, 'Hello')
assert(first.messages[1].content:find('Russian', 1, true), 'target language missing from the prompt')
assert(first.messages[1].content:find('"transliteration"', 1, true), 'Latin reading missing from the prompt')
equal(posts[1].headers.Authorization, 'Bearer sk-test')
-- Translated text must never reach a tool-enabled request; pass needs both Homebrew prefixes.
equal(first.tools, nil)
equal(first.reasoning.enabled, false)
equal(first.provider.sort, 'throughput')
assert(tasks[1].arguments[2]:find('/opt/homebrew/bin:/usr/local/bin:', 1, true), tasks[1].arguments[2])
assert(tasks[1].arguments[2]:find('pass show openrouter/api/token', 1, true), tasks[1].arguments[2])
chatReply(1, 200, answer(' Привет \n'))
equal(chooser.items[1].text, 'Привет')
typeQuery('tr de Hello'); tick()
equal(#tasks, 1)
chatReply(2, 200, answer('Hallo'))
assert(not chooser.items[1].subText:find('Hallo', 1, true), 'Latin-script output was repeated')
chooser:select(1)
equal(copied[1], 'Hallo')
""")

    def test_should_not_replace_app_results_when_an_old_translation_finishes(self):
        self.run_lua(r"""
app.show()
typeQuery('tr ru Hello'); tick()
passReply(1, 0, 'sk-test\n')
typeQuery('Safari')
chatReply(1, 200, answer('Привет'))
equal(chooser.items[1].app, '/Applications/Safari.app')
""")

    def test_should_keep_the_newest_translation_when_an_older_response_arrives_late(self):
        self.run_lua(r"""
app.show()
typeQuery('tr ru Hello'); tick()
passReply(1, 0, 'sk-test\n')
typeQuery('tr de Hello'); tick()
chatReply(2, 200, answer('Hallo'))
chatReply(1, 200, answer('Привет'))
equal(chooser.items[1].copy, 'Hallo')
""")

    def test_should_keep_translation_errors_unselectable_and_recover_on_a_valid_request(self):
        self.run_lua(r"""
app.show()
typeQuery('tr xx>en hi'); tick()
equal(chooser.items[1].text, 'Unsupported language: xx. Use one of: ar, az, de, el, en, es, fa, fr, he, hi, hy, id, it, ja, ka, ko, la, nl, pl, pt, ru, sv, tr, uk, vi, zh, zh-Hant.')
equal(#tasks + #posts, 0)
chooser:select(1)
equal(#copied, 0)
app.show()
typeQuery('tr ru hi'); tick()
passReply(1, 0, 'sk-test\n')
chatReply(1, 502, { error = { message = 'Provider returned error' } })
equal(chooser.items[1].text, 'Translation failed: Provider returned error')
equal(chooser.items[1].valid, false)
typeQuery('tr ru hello'); tick()
chatReply(2, 200, answer('привет'))
chooser:select(1)
equal(copied[1], 'привет')
""")

    def test_should_read_pass_again_after_the_key_is_rejected(self):
        self.run_lua(r"""
app.show()
typeQuery('tr ru Hello'); tick()
passReply(1, 0, 'sk-old\n')
chatReply(1, 401, { error = { message = 'User not found.' } })
equal(chooser.items[1].text, 'Translation failed: User not found.')
typeQuery('tr ru Hello again'); tick()
equal(#tasks, 2)
passReply(2, 0, 'sk-new\n')
equal(posts[2].headers.Authorization, 'Bearer sk-new')
""")

    def test_should_name_the_stated_source_and_target_languages_in_the_request(self):
        self.run_lua(r"""
app.show()
typeQuery('tr ru>en Привет'); tick()
passReply(1, 0, 'sk-test\n')
local prompt = chatRequest(1).messages[1].content
assert(prompt:find('into English', 1, true), prompt)
assert(prompt:find('The text is in Russian', 1, true), prompt)
typeQuery('tr zh-HANT hi'); tick()
assert(chatRequest(2).messages[1].content:find('into Traditional Chinese', 1, true), 'Traditional Chinese missing')
typeQuery('tr xx hi'); tick()
equal(chooser.items[1].text, 'Unsupported language: xx. Use one of: ar, az, de, el, en, es, fa, fr, he, hi, hy, id, it, ja, ka, ko, la, nl, pl, pt, ru, sv, tr, uk, vi, zh, zh-Hant.')
equal(#posts, 2)
typeQuery('tr la>en Carpe diem'); tick()
assert(chatRequest(3).messages[1].content:find('The text is in Latin', 1, true), 'Latin source missing')
typeQuery('tr uk>pt Привіт'); tick()
local added = chatRequest(4).messages[1].content
assert(added:find('into Portuguese', 1, true) and added:find('The text is in Ukrainian', 1, true), added)
""")

    def test_should_report_network_empty_and_incomplete_responses_as_failures(self):
        cases = {
            "network": (
                "posts[1].callback(-1, 'The Internet connection appears to be offline.')",
                "Translation failed: The Internet connection appears to be offline.",
            ),
            "malformed body": ("posts[1].callback(200, 'not json')", "Translation failed: empty or unreadable reply"),
            "blank content": (
                "chatReply(1, 200, { choices = { { message = { content = '  ' } } } })",
                "Translation failed: empty or unreadable reply",
            ),
            "cut off": (
                "chatReply(1, 200, { choices = { { message = { content = 'partial tra' }, finish_reason = 'length' } } })",
                "Translation failed: incomplete output (length)",
            ),
        }
        for name, (reply, expected) in cases.items():
            with self.subTest(name=name):
                self.run_lua(f"""
app.show()
typeQuery('tr ru Hello'); tick()
passReply(1, 0, 'sk-test\\n')
{reply}
equal(chooser.items[1].text, {expected!r})
equal(chooser.items[1].valid, false)
""")

    def test_should_send_only_the_newest_query_typed_while_the_key_loads(self):
        self.run_lua(r"""
app.show()
typeQuery('tr ru Hel'); tick()
typeQuery('tr ru Hello'); tick()
equal(#tasks, 1)
passReply(1, 0, 'sk-test\n')
equal(#posts, 1)
equal(chatRequest(1).messages[2].content, 'Hello')
""")

    def test_should_show_multiline_translations_on_one_row_but_copy_them_intact(self):
        self.run_lua(r"""
app.show()
typeQuery('tr ru Hello'); tick()
passReply(1, 0, 'sk-test\n')
chatReply(1, 200, answer('Строка один\nСтрока два', 'Stroka odin\nStroka dva'))
equal(chooser.items[1].text, 'Строка один Строка два')
assert(chooser.items[1].subText:find('Stroka odin Stroka dva', 1, true), chooser.items[1].subText)
chooser:select(1)
equal(copied[1], 'Строка один\nСтрока два')
""")

    def test_should_keep_a_reread_key_when_an_older_request_is_rejected_late(self):
        self.run_lua(r"""
app.show()
typeQuery('tr ru One'); tick()
passReply(1, 0, 'sk-old\n')
typeQuery('tr ru Two'); tick()
chatReply(1, 401, { error = { message = 'User not found.' } })
typeQuery('tr ru Three'); tick()
passReply(2, 0, 'sk-new\n')
chatReply(2, 401, { error = { message = 'User not found.' } })
typeQuery('tr ru Four'); tick()
equal(#tasks, 2)
equal(posts[4].headers.Authorization, 'Bearer sk-new')
""")

    def test_should_report_an_unavailable_key_without_calling_openrouter(self):
        self.run_lua(r"""
app.show()
typeQuery('tr ru Hello'); tick()
passReply(1, 1, '')
equal(chooser.items[1].text, 'OpenRouter key unavailable — check pass openrouter/api/token')
equal(chooser.items[1].valid, false)
equal(#posts, 0)
""")

    def test_should_stop_a_pending_key_lookup_when_teardown_discards_its_callback(self):
        self.run_lua(r"""
app.show()
typeQuery('tr ru Hello'); tick()
tasks[1].callback = nil
shutdown()
equal(tasks[1].running, false)
""")

    def test_should_hide_the_panel_on_shutdown_and_ignore_late_output(self):
        self.run_lua(r"""
app.show()
typeQuery('tr ru Hello'); tick()
passReply(1, 0, 'sk-test\n')
shutdown()
equal(chooser.visible, false)
local before = chooser.items[1].text
chatReply(1, 200, answer('late'))
equal(chooser.items[1].text, before)
equal(chooser.visible, false)
equal(#copied, 0)
""")

    def test_should_close_the_panel_on_escape_or_ctrl_c_with_or_without_a_query(self):
        for name, (mods, key) in DISMISS_KEYS.items():
            for query in ("", "saf"):
                with self.subTest(key=name, query=query):
                    self.run_lua(f"""
app.show()
typeQuery('{query}')
assert(press('{mods}', '{key}'), '{name} was not handled while the panel was open')
equal(chooser.visible, false)
equal(#launched, 0)
""")

    def test_should_release_the_dismiss_keys_whenever_the_panel_closes(self):
        for close in ("chooser:escape()", "app.show()", "typeQuery('safari'); chooser:select(1)", "shutdown()"):
            with self.subTest(close=close):
                self.run_lua(f"""
app.show()
{close}
equal(chooser.visible, false)
equal(press('', 'escape'), false)
equal(press('ctrl', 'c'), false)
equal(press('ctrl', 'j'), false)
equal(press('ctrl', 'k'), false)
equal(press('', 'down'), false)
""")

    def test_should_move_through_rows_with_vim_arrow_and_emacs_keys_and_wrap(self):
        for name, ((mods, key), step) in NAVIGATION_KEYS.items():
            with self.subTest(key=name):
                # The empty panel lists five commands: emoji, gh, sym, tr, ud.
                expected = [((step * n) % 5) + 1 for n in range(1, 7)]
                self.run_lua(f"""
app.show()
local rows = {{}}
for _ = 1, 6 do
  assert(press('{mods}', '{key}'), '{name} was not handled')
  rows[#rows + 1] = chooser:selectedRow()
end
equal(table.concat(rows, ','), '{",".join(map(str, expected))}')
""")

    def test_should_activate_the_row_chosen_with_ctrl_j(self):
        self.run_lua(r"""
app.show()
assert(press('ctrl', 'j'))
equal(chooser.items[chooser:selectedRow()].query, 'gh ')
chooser:select(chooser:selectedRow())
equal(chooser.queryText, 'gh ')
equal(chooser.visible, true)
""")

    def test_should_pass_every_key_through_after_closing_from_a_panel_key(self):
        for name, (mods, key) in DISMISS_KEYS.items():
            with self.subTest(key=name):
                self.run_lua(f"""
app.show()
assert(press('{mods}', '{key}'))
equal(chooser.visible, false)
for _, k in ipairs({{ {{'', 'escape'}}, {{'ctrl', 'c'}}, {{'ctrl', 'j'}}, {{'ctrl', 'k'}}, {{'ctrl', 'n'}},
    {{'ctrl', 'p'}}, {{'', 'down'}}, {{'', 'up'}}, {{'fn', 'down'}} }}) do
  equal(press(k[1], k[2]), false)
end
""")

    def test_should_move_on_real_arrow_events_and_leave_typing_and_cmd_c_alone(self):
        self.run_lua(r"""
app.show()
assert(press('fn', 'down'), 'arrow events carry the fn flag')
equal(chooser:selectedRow(), 2)
equal(press('', 'a'), false)
equal(press('', 'c'), false)
equal(press('cmd', 'c'), false)
equal(press('ctrl+shift', 'j'), false)
equal(chooser.visible, true)
""")

    def test_should_stop_a_pending_search_when_escape_closes_the_panel(self):
        self.run_lua(r"""
app.show()
typeQuery('tr ru Hello'); tick()
passReply(1, 0, 'sk-test\n')
assert(press('', 'escape'))
chatReply(1, 200, answer('Привет'))
equal(chooser.visible, false)
app.show()
assert(press('ctrl', 'c'), 'Ctrl-C was not re-enabled after reopening')
""")

    def test_should_remove_pending_github_capture_when_teardown_discards_the_task_callback(self):
        self.run_lua(r"""
app.show()
typeQuery('gh reload'); tick()
local output = tasks[1].arguments[5]
local file = assert(io.open(output, 'r'))
file:close()
tasks[1].callback = nil
shutdown()
equal(io.open(output, 'r'), nil)
""")

    def test_should_launch_the_exact_app_ahead_of_partial_name_matches(self):
        self.run_lua(r"""
app.show()
typeQuery('safari')
equal(chooser.items[1].text, 'Safari')
chooser:select(1)
equal(launched[1], '/Applications/Safari.app')
equal(#requests, 0)
""")

    def test_should_refresh_removed_and_readded_apps_without_following_directory_cycles(self):
        self.run_lua(r"""
files['/Applications'].entries = { 'Alias.app', 'Utilities', 'Loop' }
files['/Applications/Alias.app'] = { mode = 'directory', target = '/Applications/Utilities/Café.app' }
files['/Applications/Loop'] = { mode = 'directory', target = '/Applications' }
app.show()
typeQuery('Café')
equal(chooser.items[1].text, 'Café')
chooser:select(1)
equal(launched[1], '/Applications/Utilities/Café.app')
files['/Applications/Utilities/Café.app'] = nil
app.show()
typeQuery('Café')
equal(chooser.items[1].valid, false)
chooser:hide()
files['/Applications/Utilities/Café.app'] = { mode = 'directory' }
app.show()
typeQuery('Café')
equal(chooser.items[1].text, 'Café')
""")

    def test_should_distinguish_same_named_apps_by_path(self):
        self.run_lua(r"""
files['/Applications/Utilities'].entries = { 'Safari.app' }
files['/Applications/Utilities/Safari.app'] = { mode = 'directory' }
app.show()
typeQuery('Safari')
findChoice('app', '/Applications/Safari.app')
local other = findChoice('app', '/Applications/Utilities/Safari.app')
chooser:hide()
chooser.completed(other)
equal(launched[1], '/Applications/Utilities/Safari.app')
""")

    def test_should_only_reserve_a_provider_keyword_after_a_space(self):
        self.run_lua(r"""
files['/Applications'].entries = { 'Emoji.app' }
files['/Applications/Emoji.app'] = { mode = 'directory' }
app.show()
typeQuery('emoji')
equal(chooser.items[1].app, '/Applications/Emoji.app')
typeQuery('emoji ')
equal(chooser.items[1].valid, false)
equal(#requests, 0)
""")

    def test_should_not_launch_an_app_deleted_after_search(self):
        self.run_lua(r"""
app.show()
typeQuery('Safari')
files['/Applications/Safari.app'] = nil
chooser:select(1)
equal(#launched, 0)
""")

    def test_should_keep_distinct_unicode_apps_and_reject_an_unrelated_unicode_query(self):
        self.run_lua(r"""
files['/Applications'].entries = { 'Café.app', 'Résumé.app' }
files['/Applications/Café.app'] = { mode = 'directory' }
files['/Applications/Résumé.app'] = { mode = 'directory' }
app.show()
typeQuery('CAFÉ')
equal(chooser.items[1].app, '/Applications/Café.app')
typeQuery('résumé')
equal(chooser.items[1].app, '/Applications/Résumé.app')
typeQuery('über')
equal(chooser.items[1].valid, false)
""")

    def test_should_copy_signed_emoji_aliases_and_accented_case_variants(self):
        scenarios = {
            "emoji -1": "👎",
            "emoji +1": "👍",
            "emoji åland": "🇦🇽",
            "emoji PIÑATA": "🪅",
            "sym µ": "µ",
            "sym Π": "π",
        }
        for query, expected in scenarios.items():
            with self.subTest(query=query):
                self.run_lua(
                    f"app.show()\ntypeQuery('{query}'); tick()\nchooser:select(1)\nequal(copied[1], '{expected}')\n"
                )

    def test_should_require_all_query_words_even_when_a_literal_symbol_matches(self):
        self.run_lua(r"""
app.show()
typeQuery('sym µ nonexistent')
equal(chooser.items[1].valid, false)
""")

    def test_should_copy_multiword_emoji_and_named_symbols_without_opening_urls(self):
        self.run_lua(r"""
app.show()
typeQuery('emoji woman technologist'); tick()
local emoji = findChoice('copy', '👩‍💻')
chooser:hide()
chooser.completed(emoji)
equal(copied[1], '👩‍💻')
app.show()
typeQuery('sym right arrow'); tick()
chooser.completed(findChoice('copy', '→'))
equal(copied[2], '→')
equal(#opened, 0)
""")

    def test_should_search_github_with_literal_query_and_open_a_pull_request(self):
        self.run_lua(r"""
app.show()
typeQuery('gh repo:owner/repo is:pr café & tea'); tick()
equal(tasks[1].arguments[6], 'repo:owner/repo is:pr café & tea')
finishTask(1, { items = { {
  title = 'Fix search', repository_url = 'https://api.github.com/repos/owner/repo',
  number = 42, state = 'open', pull_request = {},
  html_url = 'https://github.com/owner/repo/pull/42',
} } })
equal(chooser.items[1].text, 'Fix search')
equal(chooser.items[1].subText, 'owner/repo #42 · PR · open')
chooser:select(1)
equal(opened[1], 'https://github.com/owner/repo/pull/42')
""")

    def test_should_cancel_github_work_and_ignore_its_late_response_after_switching_to_apps(self):
        self.run_lua(r"""
app.show()
typeQuery('gh chooser'); tick()
typeQuery('Safari')
finishTask(1, { items = { {
  title = 'Stale issue', repository_url = 'https://api.github.com/repos/owner/repo',
  number = 1, state = 'closed', html_url = 'https://github.com/owner/repo/issues/1',
} } })
equal(tasks[1].terminated, true)
equal(chooser.items[1].text, 'Safari')
""")

    def test_should_remove_github_results_on_authentication_failure(self):
        self.run_lua(r"""
app.show()
typeQuery('gh first'); tick()
finishTask(1, { items = { {
  title = 'Issue', repository_url = 'https://api.github.com/repos/owner/repo',
  number = 1, state = 'closed', html_url = 'https://github.com/owner/repo/issues/1',
} } })
typeQuery('gh second'); tick()
finishTask(2, {}, 4)
equal(chooser.items[1].valid, false)
chooser:select(1)
equal(#opened, 0)
""")

    def test_should_cancel_without_opening_a_page_when_loading_status_is_activated(self):
        self.run_lua(r"""
app.show()
typeQuery('ud yeet'); tick()
chooser:select(1)
chooser:escape()
respond(1, { 'stale result' })
equal(chooser.visible, false)
equal(#opened, 0)
equal(#requests, 1)
""")

    def test_should_show_highest_voted_matching_definition_and_open_its_page(self):
        self.run_lua(r"""
app.show()
typeQuery('ud yeet'); tick()
respond(1, { 'yeet' })
respond(2, { list = {
  { word = 'Yeet', definition = 'less popular', thumbs_up = 2, defid = 11 },
  { word = 'unrelated', definition = 'wrong term', thumbs_up = 1000, defid = 99 },
  { word = 'YEET', definition = 'To [throw]\r\n forcefully', thumbs_up = 90, defid = 22 },
  { word = 'yeet', definition = 'later tie', thumbs_up = 90, defid = 33 },
} })
equal(chooser.items[1].text, 'yeet')
equal(chooser.items[1].subText, 'To throw forcefully')
chooser.completed(chooser.items[1])
equal(opened[1], 'https://www.urbandictionary.com/define.php?term=yeet&defid=22')
""")

    def test_should_ignore_old_results_after_same_query_is_reentered(self):
        self.run_lua(r"""
app.show()
typeQuery('ud yeet'); tick()
respond(1, { 'yeet' })
typeQuery('ud yeetus'); tick()
typeQuery('ud yeet'); tick()
respond(4, { 'yeet' })
respond(5, { list = { { word = 'yeet', definition = 'current', thumbs_up = 1, defid = 5 } } })
respond(2, { list = { { word = 'yeet', definition = 'stale', thumbs_up = 900, defid = 2 } } })
respond(3, { 'yeetus' })
equal(chooser.items[1].subText, 'current')
equal(#requests, 5)
""")

    def test_should_cancel_pending_work_across_close_and_reopen(self):
        self.run_lua(r"""
app.show()
typeQuery('ud yeet'); tick()
respond(1, { 'yeet' })
chooser:hide()
app.show()
respond(2, { list = { { word = 'yeet', definition = 'stale', defid = 2 } } })
chooser.completed(nil)
equal(findChoice('query', 'ud ').query, 'ud ')
equal(#opened, 0)
equal(#requests, 2)
""")

    def test_should_keep_suggestion_order_when_definitions_arrive_out_of_order(self):
        self.run_lua(r"""
app.show()
typeQuery('ud café & tea'); tick()
equal(requests[1].url, 'https://api.urbandictionary.com/v0/autocomplete?term=caf%C3%A9%20%26%20tea')
respond(1, { 'café & tea', 'tea time' })
respond(3, { list = { { word = 'tea time', definition = 'second', defid = 3 } } })
respond(2, { list = { { word = 'café & tea', definition = 'first', defid = 2 } } })
equal(chooser.items[1].text, 'café & tea')
equal(chooser.items[2].text, 'tea time')
chooser.completed(chooser.items[1])
equal(opened[1], 'https://www.urbandictionary.com/define.php?term=caf%C3%A9%20%26%20tea&defid=2')
""")

    def test_should_clear_old_choices_before_debounce_and_empty_prefix(self):
        self.run_lua(r"""
app.show()
typeQuery('ud yeet'); tick()
respond(1, { 'yeet' })
typeQuery('ud new')
equal(chooser.items[1].valid, false)
typeQuery('ud '); tick()
equal(chooser.items[1].valid, false)
equal(#requests, 2)
""")

    def test_should_expose_network_failure_without_a_selectable_stale_entry(self):
        self.run_lua(r"""
app.show()
typeQuery('ud yeet'); tick()
respond(1, {}, 503)
equal(chooser.items[1].valid, false)
chooser.completed(chooser.items[1])
equal(#opened, 0)
""")

    def test_should_leave_no_selectable_result_when_autocomplete_is_empty(self):
        self.run_lua(r"""
app.show()
typeQuery('ud missing'); tick()
respond(1, {})
equal(chooser.items[1].valid, false)
chooser.completed(chooser.items[1])
equal(#opened, 0)
equal(#requests, 1)
""")

    def test_should_keep_terms_openable_when_definition_is_missing_or_malformed(self):
        self.run_lua(r"""
app.show()
typeQuery('ud unknown'); tick()
respond(1, { 'unknown', 'other' })
respond(2, { list = {} })
requests[3].callback(200, 'not json')
equal(chooser.items[1].text, 'unknown')
equal(chooser.items[2].text, 'other')
chooser.completed(chooser.items[1])
equal(opened[1], 'https://www.urbandictionary.com/define.php?term=unknown')
""")

    def test_should_open_an_empty_shared_panel_and_select_its_ud_provider(self):
        self.run_lua(r"""
app.show()
equal(chooser.queryText, '')
local choice = findChoice('query', 'ud ')
chooser:hide()
chooser.completed(choice)
equal(chooser.queryText, 'ud ')
typeQuery('ud yeet'); tick()
respond(1, { 'yeet' })
respond(2, { list = { { word = 'yeet', definition = 'inline definition', defid = 7 } } })
equal(chooser.items[1].subText, 'inline definition')
chooser:select(1)
equal(opened[1], 'https://www.urbandictionary.com/define.php?term=yeet&defid=7')
""")

    def test_should_discard_ud_work_when_switching_to_an_unknown_keyword(self):
        self.run_lua(r"""
app.show()
typeQuery('ud yeet'); tick()
respond(1, { 'yeet' })
typeQuery('unknown query')
respond(2, { list = { { word = 'yeet', definition = 'stale', defid = 2 } } })
equal(chooser.items[1].valid, false)
equal(#requests, 2)
""")

    def test_should_toggle_on_two_command_taps_without_consuming_input(self):
        self.run_lua(r"""
emit(1, 55, { cmd = true }, 0.00)
emit(1, 55, {}, 0.04)
emit(1, 54, { cmd = true }, 0.14)
emit(1, 54, {}, 0.18)
equal(chooser.visible, true)
equal(chooser.queryText, '')
emit(1, 55, { cmd = true }, 0.30)
emit(1, 55, {}, 0.34)
emit(1, 55, { cmd = true }, 0.44)
emit(1, 55, {}, 0.48)
equal(chooser.visible, false)
""")

    def test_should_accept_the_system_double_tap_interval_boundary(self):
        self.run_lua(r"""
emit(1, 55, { cmd = true }, 0.00)
emit(1, 55, {}, 0.01)
emit(1, 55, { cmd = true }, 0.40)
emit(1, 55, {}, 0.41)
equal(chooser.visible, true)
""")

    def test_should_reject_incomplete_slow_or_chorded_command_gestures(self):
        scenarios = {
            "single tap": """
emit(1, 55, { cmd = true }, 0.00)
emit(1, 55, {}, 0.04)
""",
            "just outside interval": """
emit(1, 55, { cmd = true }, 0.00)
emit(1, 55, {}, 0.01)
emit(1, 55, { cmd = true }, 0.40)
emit(1, 55, {}, 0.410001)
""",
            "long first hold": """
emit(1, 55, { cmd = true }, 0.00)
emit(1, 55, {}, 0.50)
emit(1, 55, { cmd = true }, 0.60)
emit(1, 55, {}, 0.64)
""",
            "command shortcut": """
emit(1, 55, { cmd = true }, 0.00)
emit(2, 8, { cmd = true }, 0.02)
emit(1, 55, {}, 0.04)
emit(1, 55, { cmd = true }, 0.14)
emit(1, 55, {}, 0.18)
""",
            "typed key between taps": """
emit(1, 55, { cmd = true }, 0.00)
emit(1, 55, {}, 0.04)
emit(2, 8, {}, 0.10)
emit(1, 55, { cmd = true }, 0.14)
emit(1, 55, {}, 0.18)
""",
            "another modifier": """
emit(1, 55, { cmd = true }, 0.00)
emit(1, 55, {}, 0.04)
emit(1, 55, { cmd = true }, 0.14)
emit(1, 56, { cmd = true, shift = true }, 0.15)
emit(1, 56, { cmd = true }, 0.16)
emit(1, 55, {}, 0.18)
""",
            "mouse shortcut": """
emit(1, 55, { cmd = true }, 0.00)
emit(3, 0, { cmd = true }, 0.02)
emit(1, 55, {}, 0.04)
emit(1, 55, { cmd = true }, 0.14)
emit(1, 55, {}, 0.18)
""",
            "both command keys held": """
emit(1, 55, { cmd = true }, 0.00)
emit(1, 54, { cmd = true }, 0.02)
emit(1, 54, { cmd = true }, 0.04)
emit(1, 55, {}, 0.06)
emit(1, 55, { cmd = true }, 0.14)
emit(1, 55, {}, 0.18)
""",
        }
        for name, scenario in scenarios.items():
            with self.subTest(name=name):
                self.run_lua(scenario + "\nequal(chooser.visible, false)\nequal(#opened, 0)\n")

    def test_should_recover_after_both_command_keys_are_held_and_released(self):
        release_orders = {
            "right released first": """
emit(1, 54, { cmd = true }, 0.04)
emit(1, 55, {}, 0.06)
""",
            "left released first": """
emit(1, 55, { cmd = true }, 0.04)
emit(1, 54, {}, 0.06)
""",
        }
        for name, release in release_orders.items():
            with self.subTest(name=name):
                self.run_lua(
                    """
emit(1, 55, { cmd = true }, 0.00)
emit(1, 54, { cmd = true }, 0.02)
"""
                    + release
                    + """
equal(chooser.visible, false)
emit(1, 55, { cmd = true }, 0.20)
emit(1, 55, {}, 0.24)
emit(1, 55, { cmd = true }, 0.34)
emit(1, 55, {}, 0.38)
equal(chooser.visible, true)
"""
                )

    def test_should_allow_a_fresh_double_tap_after_a_command_shortcut(self):
        self.run_lua(r"""
emit(1, 55, { cmd = true }, 0.00)
emit(2, 8, { cmd = true }, 0.02)
emit(1, 55, {}, 0.04)
emit(1, 55, { cmd = true }, 0.14)
emit(1, 55, {}, 0.18)
emit(1, 55, { cmd = true }, 0.24)
emit(1, 55, {}, 0.28)
equal(chooser.visible, true)
""")


if __name__ == "__main__":
    unittest.main()
