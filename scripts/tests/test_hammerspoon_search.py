from __future__ import annotations

import os
import shutil
import subprocess
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
local requests, timers, opened = {}, {}, {}
local event_callback
local chooser = { visible = false, items = {} }
local function copy(value)
  if type(value) ~= 'table' then return value end
  local result = {}
  for key, item in pairs(value) do result[key] = copy(item) end
  return result
end
function chooser:choices(items) self.items = copy(items); return self end
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
function chooser:placeholderText(text) return self end
function chooser:rows(rows) return self end
function chooser:width(width) return self end
local payloads = {}
hs = {
  chooser = { new = function(fn) chooser.completed = fn; return chooser end },
  eventtap = {
    keyStroke = function() end,
    doubleClickInterval = function() return 0.4 end,
    event = { types = { flagsChanged = 1, keyDown = 2, leftMouseDown = 3, rightMouseDown = 4, otherMouseDown = 5, scrollWheel = 6 } },
    new = function(_, fn)
      event_callback = fn
      return { start = function(self) return self end }
    end,
  },
  timer = { doAfter = function(_, fn)
    local timer = { callback = fn, stop = function(self) self.stopped = true end }
    timers[#timers + 1] = timer
    return timer
  end },
  http = { asyncGet = function(url, _, fn)
    requests[#requests + 1] = { url = url, callback = fn }
  end },
  json = { decode = function(body)
    if not payloads[body] then error('invalid JSON') end
    return payloads[body]
  end },
  urlevent = { openURL = function(url) opened[#opened + 1] = url; return true end },
}
package.preload.urban_dictionary = function() return dofile(arg[2]) end
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
local function equal(actual, expected)
  assert(actual == expected, 'expected ' .. tostring(expected) .. ', got ' .. tostring(actual))
end
"""


class TestHammerspoonSearch(unittest.TestCase):
    """WHEN the live chooser receives asynchronous search responses."""

    def run_lua(self, scenario: str):
        self.assertIsNotNone(LUA, "An installed Lua interpreter must be discoverable on PATH or beside its mise shim")
        result = subprocess.run(
            [LUA, "-", str(MODULE), str(PROVIDER), str(GESTURE)],
            input=HARNESS + scenario,
            check=False,
            capture_output=True,
            text=True,
            cwd=REPO,
            timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

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
equal(chooser.items[1].query, 'ud ')
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
equal(chooser.items[1].query, 'ud ')
chooser:select(1)
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
