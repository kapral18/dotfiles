local wezterm = require("wezterm")
local mux = wezterm.mux

local hyperlink_rules = {
	-- Linkify things that look like URLs
	-- This is actually the default if you don't specify any hyperlink_rules
	{
		regex = "\\b\\w+://(?:[\\w.-]+)\\.[a-z]{2,15}\\S*\\b",
		format = "$0",
	},

	-- linkify email addresses
	{
		regex = "\\b\\w+@[\\w-]+(\\.[\\w-]+)+\\b",
		format = "mailto:$0",
	},

	-- file:// URI
	{
		regex = "\\bfile://\\S*\\b",
		format = "$0",
	},

	-- Matches: a URL in parens: (URL)
	{
		regex = "\\((\\w+://\\S+)\\)",
		format = "$1",
		highlight = 1,
	},
	-- Matches: a URL in brackets: [URL]
	{
		regex = "\\[(\\w+://\\S+)\\]",
		format = "$1",
		highlight = 1,
	},
	-- Matches: a URL in curly braces: {URL}
	{
		regex = "\\{(\\w+://\\S+)\\}",
		format = "$1",
		highlight = 1,
	},
	-- Matches: a URL in angle brackets: <URL>
	{
		regex = "<(\\w+://\\S+)>",
		format = "$1",
		highlight = 1,
	},
	-- Then handle URLs not wrapped in brackets
	{
		regex = "\\b\\w+://\\S+[)/a-zA-Z0-9-]+",
		format = "$0",
	},
	-- implicit mailto link
	{
		regex = "\\b\\w+@[\\w-]+(\\.[\\w-]+)+\\b",
		format = "mailto:$0",
	},

	-- make username/project paths clickable. this implies paths like the following are for github.
	-- ( "nvim-treesitter/nvim-treesitter" | wbthomason/packer.nvim | wez/wezterm | "wez/wezterm.git" )
	-- as long as a full url hyperlink regex exists above this it should not match a full url to
	-- github or gitlab / bitbucket (i.e. https://gitlab.com/user/project.git is still a whole clickable url)
	{
		regex = [[["]?([\w\d]{1}[-\w\d]+)(/){1}([-\w\d\.]+)["]?]],
		format = "https://www.github.com/$1/$3",
	},
}

local is_maximized = false

-- maximize on start
wezterm.on("gui-startup", function(cmd)
	local tab, pane, window = mux.spawn_window(cmd or {})
	window:gui_window():maximize()
	is_maximized = true
end)

wezterm.on("toggle_maximize", function(window, pane)
	if is_maximized then
		window:restore()
		is_maximized = false
	else
		window:maximize()
		is_maximized = true
	end
end)

local keys = {
	-- CTRL-SHIFT-l activates the debug overlay
	{ key = "L", mods = "CTRL", action = wezterm.action.ShowDebugOverlay },
	{ key = "m", mods = "CMD", action = wezterm.action({ EmitEvent = "toggle_maximize" }) },
	{ key = "q", mods = "CMD", action = wezterm.action.QuitApplication },
	{ key = "w", mods = "CMD", action = wezterm.action.CloseCurrentTab({ confirm = false }) },
	{
		key = "0",
		mods = "CMD",
		action = wezterm.action.ResetFontAndWindowSize,
	},
	{
		key = "RightArrow",
		mods = "ALT|CMD",
		action = wezterm.action({ ActivateTabRelative = 1 }),
	},
	{
		key = "LeftArrow",
		mods = "ALT|CMD",
		action = wezterm.action({ ActivateTabRelative = -1 }),
	},
	{
		key = "n",
		mods = "CMD",
		action = wezterm.action({ SpawnTab = "CurrentPaneDomain" }),
	},
	{
		key = "f",
		mods = "CMD",
		action = wezterm.action({ Search = { CaseSensitiveString = "" } }),
	},
	-- Add basic ctrl + c, ctrl + v from defaults
	{
		key = "c",
		mods = "CMD",
		action = wezterm.action({ CopyTo = "Clipboard" }),
	},
	{
		key = "v",
		mods = "CMD",
		action = wezterm.action({ PasteFrom = "Clipboard" }),
	},
}

return {
	color_scheme = "Catppuccin Mocha",
	enable_scroll_bar = true,
	disable_default_key_bindings = true,
	font = wezterm.font("JetBrainsMono Nerd Font"),
	font_size = 12,
	hide_tab_bar_if_only_one_tab = true,
	hyperlink_rules = hyperlink_rules,
	keys = keys,
	scrollback_lines = 10000,
	tab_bar_at_bottom = true,
	use_resize_increments = true,
	use_fancy_tab_bar = false,
	macos_window_background_blur = 30,
	window_background_opacity = 1,
	scroll_to_bottom_on_input = true,
	quick_select_patterns = {
		-- match things that look like sha1 hashes
		-- (this is actually one of the default patterns)
		"[0-9a-f]{7,40}",
	},
	front_end = "WebGpu",
	webgpu_power_preference = "HighPerformance",
	window_decorations = "INTEGRATED_BUTTONS|RESIZE",
	window_padding = {
		left = 10,
		right = 5,
		top = 10,
		bottom = 0,
	},
	window_close_confirmation = "NeverPrompt",
	adjust_window_size_when_changing_font_size = false,
	text_background_opacity = 1,
}
