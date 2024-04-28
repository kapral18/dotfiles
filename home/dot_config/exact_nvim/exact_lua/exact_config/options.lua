-- Options are automatically loaded before lazy.nvim startup
-- Default options that are always set: https://github.com/LazyVim/LazyVim/blob/main/lua/lazyvim/config/options.lua
-- Add any additional options here
vim.opt.winbar = "%=%m %f"
vim.opt.conceallevel = 0 -- Do not hide * markup for bold and italic
vim.opt.relativenumber = false -- Show relative line numbers
vim.opt.wrap = false -- Dislable line wrap
vim.opt.breakindent = true -- Keep indentation on wrapped lines
vim.opt.pumblend = 0 -- disable transparency in popup menu

-- Chars {{{
vim.opt.list = true
vim.opt.listchars = {
  tab = "  ",
  trail = "·",
  extends = "◣",
  precedes = "◢",
  nbsp = "○",
}

-- Wildmenu {{{
vim.opt.wildignorecase = true

-- stuff to ignore when tab completing
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
-- }}}

-- adds <> to % matchpairs
vim.opt.matchpairs:append("<:>")
vim.opt.complete = ".,w,b,u,t,i"
vim.opt.nrformats = "bin,hex,alpha" -- can increment alphabetically too!

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

vim.g.python3_host_prog = "/opt/homebrew/Caskroom/miniconda/base/bin/python3"
