-- Options are automatically loaded before lazy.nvim startup
-- Default options that are always set: https://github.com/LazyVim/LazyVim/blob/main/lua/lazyvim/config/options.lua

table.unpack = table.unpack or unpack

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
