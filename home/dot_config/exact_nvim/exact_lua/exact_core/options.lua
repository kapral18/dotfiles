table.unpack = table.unpack or unpack

local opt = vim.opt

vim.g.mapleader = " "
vim.g.maplocalleader = "\\"

opt.autowrite = true
opt.clipboard = vim.env.SSH_CONNECTION and "" or "unnamedplus"
opt.completeopt = "menu,menuone,noselect"
opt.confirm = true
opt.cursorline = true
opt.expandtab = true
opt.fillchars = {
  foldopen = "",
  foldclose = "",
  fold = " ",
  foldsep = " ",
  diff = "╱",
  eob = " ",
}
opt.foldlevel = 99
opt.foldmethod = "indent"
opt.foldtext = ""
opt.formatexpr = "v:lua.require'util'.format.formatexpr()"
opt.formatoptions = "jcroqlnt"
opt.grepformat = "%f:%l:%c:%m"
opt.grepprg = "rg --vimgrep"
opt.ignorecase = true
opt.inccommand = "nosplit"
opt.jumpoptions = "clean"
opt.laststatus = 3
opt.linebreak = true
opt.list = true
opt.mouse = "a"
opt.number = true
opt.pumblend = 0
opt.pumheight = 10
opt.relativenumber = false
opt.ruler = false
opt.scrolloff = 4
opt.sessionoptions = { "buffers", "tabpages", "winsize", "winpos", "localoptions" }
opt.shiftround = true
opt.shiftwidth = 2
opt.shortmess:append({ W = true, I = true, c = true, C = true })
opt.showmode = false
opt.sidescrolloff = 8
opt.signcolumn = "yes"
opt.smartcase = true
opt.smartindent = true
opt.smoothscroll = true
opt.spelllang = { "en" }
opt.splitbelow = true
opt.splitkeep = "screen"
opt.splitright = true
opt.statuscolumn = [[]]
opt.tabstop = 2
opt.termguicolors = true
opt.timeoutlen = vim.g.vscode and 1000 or 300
opt.undofile = true
opt.undolevels = 10000
opt.updatetime = 200
opt.virtualedit = "block"
opt.wildmode = "longest:full,full"
opt.winminwidth = 5
opt.wrap = false
opt.breakindent = true
opt.swapfile = false
opt.winhighlight = "Winbar:StatsLine,WinbarNC:StatusLineNC"
opt.history = 10000
opt.complete = ".,w,b,u,t,i,k"
opt.fixendofline = false

opt.listchars = {
  tab = "  ",
  trail = "·",
  extends = "◣",
  precedes = "◢",
  nbsp = "○",
}

opt.wildignorecase = true
opt.wildignore = {
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

opt.showmatch = true
opt.matchtime = 2
opt.matchpairs:append("<:>")
opt.nrformats = "bin,hex,alpha"

vim.g.matchparen_timeout = 2
vim.g.matchparen_insert_timeout = 2

opt.path:append("**")
opt.conceallevel = 0

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

vim.g.snacks_animate = false
