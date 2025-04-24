-- Options are automatically loaded before lazy.nvim startup
-- Default options that are always set: https://github.com/LazyVim/LazyVim/blob/main/lua/lazyvim/config/options.lua

table.unpack = table.unpack or unpack

local function _get_path_from_cwd()
  local full_path = vim.fn.expand("%:p")
  if full_path == "" then
    return nil, nil
  end -- No path

  local cwd = vim.fn.getcwd()
  local path_sep = package.config:sub(1, 1) -- '/' or '\'
  if cwd:sub(-1) ~= path_sep then
    cwd = cwd .. path_sep
  end

  local is_in_cwd = (full_path:find(cwd, 1, true) == 1)
  local relative_path

  if is_in_cwd then
    relative_path = full_path:sub(#cwd + 1)
    if relative_path == "" then
      relative_path = "."
    end -- Is CWD root
  else
    -- Outside CWD: Use path relative to root/drive as default
    relative_path = vim.fn.fnamemodify(full_path, ":.")
    -- Optional: Could fallback to filename if relative-to-root is still absolute
  end
  return relative_path, is_in_cwd
end

local function get_bufferline_component_count(num_total_components, is_in_cwd)
  if num_total_components == 0 then
    return 0
  end

  local count = 0
  if is_in_cwd then
    -- Bufferline shows filename + up to 2 parents = max 3 components
    count = math.min(num_total_components, 3)
  else
    -- If outside CWD, assume bufferline shows only filename effectively
    -- Adjust this assumption if your bufferline logic differs for non-CWD files
    count = math.min(num_total_components, 1) -- Just filename assumption
  end
  return count
end

function Get_winbar_remainder_path()
  -- 1. Get path info
  local relative_path, is_in_cwd = _get_path_from_cwd()
  if not relative_path or relative_path == "." then
    return "" -- No path or is CWD root (handled by bufferline)
  end

  local path_sep = package.config:sub(1, 1)
  local path_components = vim.split(relative_path, path_sep, { trimempty = true })
  local num_total_components = #path_components

  if num_total_components == 0 then
    return "" -- Path was likely just "/" or empty after trim
  end

  -- 2. Determine components for winbar
  local bufferline_count = get_bufferline_component_count(num_total_components, is_in_cwd)
  local winbar_end_index = num_total_components - bufferline_count

  if winbar_end_index <= 0 then
    return "" -- All components covered by bufferline, winbar is empty
  end

  -- Extract components specifically for the winbar
  local winbar_components = {}
  for i = 1, winbar_end_index do
    table.insert(winbar_components, path_components[i])
  end

  if #winbar_components == 0 then
    return "" -- Should be redundant due to winbar_end_index check, but safe
  end

  -- 3. Define constants and get available width
  local available_width = vim.fn.winwidth(0)
  local trailing_sep = path_sep -- Separator *after* winbar content
  local ellipsis = "..." -- Ellipsis for *leading* truncation within winbar part
  local trailing_sep_width = vim.fn.strdisplaywidth(trailing_sep)
  local ellipsis_width = vim.fn.strdisplaywidth(ellipsis)

  -- Minimal space needed is for the trailing separator (if content exists)
  -- Or potentially just the ellipsis if content gets fully truncated
  if available_width < 1 then
    return ""
  end -- Practically no space

  -- 4. Check if full winbar components fit *with* the trailing separator
  local full_winbar_string = table.concat(winbar_components, path_sep)
  local full_winbar_width = vim.fn.strdisplaywidth(full_winbar_string)

  if full_winbar_width + trailing_sep_width <= available_width then
    -- The whole winbar part fits, return it with the trailing separator
    return full_winbar_string .. trailing_sep
  end

  -- 5. Truncation is needed. Calculate max width for content *between* ellipsis and trailing sep
  local max_content_width = available_width - ellipsis_width - trailing_sep_width

  -- If max_content_width is negative, only ellipsis/separator might fit
  if max_content_width < 0 then
    if ellipsis_width + trailing_sep_width <= available_width then
      return ellipsis .. trailing_sep -- Fits ".../"
    elseif ellipsis_width <= available_width then
      return ellipsis -- Fits "..."
    else
      return "" -- Not even ellipsis fits
    end
  end

  -- Find the rightmost components that fit within max_content_width
  local truncated_content = ""
  local current_content_width = 0
  for i = #winbar_components, 1, -1 do
    local component = winbar_components[i]
    local component_width = vim.fn.strdisplaywidth(component)
    -- Separator *before* this component if content already exists
    local sep_to_add = (current_content_width > 0) and path_sep or ""
    local sep_width = vim.fn.strdisplaywidth(sep_to_add)

    if component_width + sep_width + current_content_width <= max_content_width then
      -- Prepend component and separator
      truncated_content = component .. sep_to_add .. truncated_content
      current_content_width = current_content_width + component_width + sep_width
    else
      -- Cannot add this component (from the left); stop building
      break
    end
  end

  -- 6. Construct final string based on truncated_content
  if truncated_content ~= "" then
    -- We managed to fit some components
    return ellipsis .. truncated_content .. trailing_sep
  else
    -- No components fit within max_content_width
    -- Fallback to just ellipsis + separator or just ellipsis if possible
    if ellipsis_width + trailing_sep_width <= available_width then
      return ellipsis .. trailing_sep
    elseif ellipsis_width <= available_width then
      return ellipsis
    else
      return ""
    end
  end
end

-- ==========================================================================
-- Configuration: Set winbar option and autocommands
-- Place this where your Neovim options are set (e.g., your init.lua)
-- ==========================================================================

-- Ensure the Lua functions above are defined before this line

-- Set the winbar option using dynamic evaluation '%{...%}' and right-alignment '%='
vim.opt.winbar = "%{%v:lua.Get_winbar_remainder_path()%}%="

-- Autocommands setup to refresh winbar on relevant events
local winbar_update_group = vim.api.nvim_create_augroup("WinbarUpdate", { clear = true })
vim.api.nvim_create_autocmd({ "WinResized", "BufEnter", "WinEnter", "DirChanged" }, {
  group = winbar_update_group,
  pattern = "*",
  desc = "Update winbar remainder path",
  callback = function()
    -- Force re-evaluation by re-assigning the option to itself.
    -- Neovim's expression evaluation will call the Lua function again.
    vim.opt.winbar = vim.opt.winbar
    -- Optional: If updates seem delayed, uncommenting this might help, but try without first.
    -- vim.cmd('redrawstatus!')
  end,
})

-- Set the session options to save and restore
-- 'buffers'  : save and restore buffers
-- 'tabpages' : save and restore tab pages
-- 'winsize'  : save and restore window sizes
-- 'winpos'   : save and restore window positions
-- 'terminal' : save and restore terminal buffers
-- 'localoptions' : save and restore local options
vim.opt.sessionoptions = "buffers,tabpages,winsize,winpos,localoptions"

-- Set specific highlights for the window bar
-- Winbar:StatsLine      : use StatusLine highlight for active window's bar
-- WinbarNC:StatusLineNC : use StatusLineNC highlight for inactive window's bar
vim.opt.winhighlight = "Winbar:StatsLine,WinbarNC:StatusLineNC"

-- Set the completion options for insert mode
-- .  - current buffer
-- w  - buffers in windows
-- b  - other loaded buffers
-- u  - unloaded buffers
-- t  - tags
-- i  - included files
-- k  - dictionary
vim.opt.complete = ".,w,b,u,t,i,k"

-- Set the number of commands to remember in history
vim.opt.history = 10000

-- Set the jump options
-- 'jumpoptions' controls how Neovim handles the jump list (CTRL-O and CTRL-I navigation)
-- Available options:
--   'stack': Makes each window maintain its own separate jump list history
--   'view': Saves the view (viewport position, folds, etc.) when adding a jump
--   'clear': Removes jumps that do not resolve to valid buffer positions
--   Multiple options can be combined like: "stack,view,clear"
vim.opt.jumpoptions = "clean"

-- Control whether Neovim adds a newline at end of file
-- When false, Neovim will not automatically add a newline at EOF
-- Useful for maintaining exact file contents without modifications
-- Some file formats or systems don't require trailing newlines
vim.opt.fixendofline = false

-- overriding lazyvim statuscolumn
vim.opt.statuscolumn = [[]]

vim.opt.path:append("**")

vim.opt.conceallevel = 0
vim.opt.number = true -- Show line numbers
vim.opt.relativenumber = false -- Show relative line numbers
vim.opt.wrap = false -- Dislable line wrap
vim.opt.breakindent = true -- Keep indentation on wrapped lines
vim.opt.pumblend = 0 -- disable transparency in popup menu
vim.opt.swapfile = false -- Disable swap file

vim.opt.list = true
vim.opt.listchars = {
  tab = "  ",
  trail = "·",
  extends = "◣",
  precedes = "◢",
  nbsp = "○",
}

-- Ignore case when completing file names
vim.opt.wildignorecase = true

-- Ignore these files when using wildmenu
vim.opt.wildignore = {
  "*~",
  "*.o",
  "*.obj",
  "*.so",
  "*vim/backups*",
  "*.git/**",
  "**/.git/**",
  "*sass-cache*",
  "*DS_Store*",
  "vendor/rails/**",
  "vendor/cache/**",
  "*.gem",
  "*.pyc",
  "log/**",
  "*.gif",
  "*.zip",
  "*.bg2",
  "*.gz",
  "*.db",
  "**/node_modules/**",
  "**/bin/**",
  "**/thesaurus/**",
}

vim.opt.showmatch = true -- Show matching brackets
vim.opt.matchtime = 2 -- Tenths of a second to show matching brackets
-- adds <> to % matchpairs
vim.opt.matchpairs:append("<:>")
-- Set the number format options for <C-a> and <C-x> increment/decrement commands
-- 'bin': recognize binary numbers (e.g. 0b1010)
-- 'hex': recognize hexadecimal numbers (e.g. 0xFF)
-- 'alpha': enable incrementing/decrementing letters (a->b->c)
vim.opt.nrformats = "bin,hex,alpha"

-- https://vi.stackexchange.com/a/5318/12823
vim.g.matchparen_timeout = 2
vim.g.matchparen_insert_timeout = 2

vim.filetype.add({
  extension = {
    log = "log",
    conf = "conf",
    env = "dotenv",
    mdx = "mdx",
    jsonl = "jsonl",
  },
  filename = {
    [".env"] = "dotenv",
    ["env"] = "dotenv",
    ["tsconfig.json"] = "jsonc",
    [".*/kitty/.+%.conf"] = "kitty",
  },
  pattern = {
    -- INFO: Match filenames like - ".env.example", ".env.local" and so on
    ["%.env%.[%w_.-]+"] = "dotenv",
    [".*%.yaml%.tmpl$"] = "gotexttmpl",
    [".*%.toml%.tmpl$"] = "gotexttmpl",
    [".*%.json%.tmpl$"] = "gotexttmpl",
    [".*%.jsonc%.tmpl$"] = "gotexttmpl",
    ["Dockerfile.*"] = "dockerfile",
    [".gitconfig.*"] = "gitconfig",
  },
})

vim.g.loaded_python3_provider = 0
vim.g.loaded_ruby_provider = 0
vim.g.loaded_perl_provider = 0
vim.g.loaded_node_provider = 0
vim.opt.syntax = "off"

vim.o.spell = false

vim.o.foldenable = false

vim.lsp.set_log_level("off")

vim.g.snacks_animate = false

---

vim.g.lazyvim_cmp = "nvim-cmp"
vim.g.lazyvim_picker = "fzf"

vim.g.neovide_input_macos_option_key_is_meta = "only_left"
