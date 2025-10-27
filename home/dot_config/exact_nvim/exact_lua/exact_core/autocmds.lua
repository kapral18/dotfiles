local augroup = vim.api.nvim_create_augroup
local autocmd = vim.api.nvim_create_autocmd

local util = require("util")
if util.config and util.config.icons and util.config.icons.diagnostics then
  local icons = util.config.icons.diagnostics
  for name, icon in pairs(icons) do
    local hl = "DiagnosticSign" .. name
    vim.fn.sign_define(hl, { text = icon, texthl = hl, numhl = "" })
  end
end

local general = augroup("k18_general", { clear = true })

autocmd({ "FocusGained", "TermClose", "TermLeave" }, {
  group = general,
  callback = function()
    if vim.o.buftype ~= "nofile" then
      vim.cmd.checktime()
    end
  end,
})

autocmd("TextYankPost", {
  group = general,
  callback = function()
    pcall(vim.highlight.on_yank, { higroup = "IncSearch", timeout = 250 })
  end,
})

autocmd("VimResized", {
  group = general,
  callback = function()
    local current = vim.fn.tabpagenr()
    vim.cmd("tabdo wincmd =")
    vim.cmd("tabnext " .. current)
  end,
})

local last_loc = augroup("k18_last_loc", { clear = true })

autocmd("BufReadPost", {
  group = last_loc,
  callback = function(event)
    local exclude = { "gitcommit" }
    local buf = event.buf
    if vim.tbl_contains(exclude, vim.bo[buf].filetype) or vim.b[buf].k18_last_loc then
      return
    end
    vim.b[buf].k18_last_loc = true
    local mark = vim.api.nvim_buf_get_mark(buf, '"')
    local lcount = vim.api.nvim_buf_line_count(buf)
    if mark[1] > 0 and mark[1] <= lcount then
      pcall(vim.api.nvim_win_set_cursor, 0, mark)
    end
  end,
})

local close_with_q_patterns = {
  "PlenaryTestPopup",
  "checkhealth",
  "dbout",
  "gitsigns-blame",
  "grug-far",
  "help",
  "lspinfo",
  "neotest-output",
  "neotest-output-panel",
  "neotest-summary",
  "notify",
  "qf",
  "spectre_panel",
  "startuptime",
  "tsplayground",
  "aerial-nav",
  "chatpgpt",
  "diagmsg",
  "fzf",
  "dap-float",
  "dap-repl",
  "scratch",
}

autocmd("FileType", {
  group = augroup("k18_close_with_q", { clear = true }),
  pattern = close_with_q_patterns,
  callback = function(event)
    vim.bo[event.buf].buflisted = false
    vim.keymap.set("n", "q", "<cmd>close<CR>", { buffer = event.buf, silent = true })
  end,
})

autocmd("FileType", {
  group = augroup("k18_man_unlisted", { clear = true }),
  pattern = "man",
  callback = function(event)
    vim.bo[event.buf].buflisted = false
  end,
})

autocmd("FileType", {
  group = augroup("k18_wrap_spell", { clear = true }),
  pattern = { "text", "plaintex", "typst", "gitcommit" },
  callback = function()
    vim.opt_local.wrap = true
    vim.opt_local.spell = true
  end,
})

-- Markdown: disable wrap (override default behavior)
autocmd("FileType", {
  group = augroup("k18_markdown", { clear = true }),
  pattern = "markdown",
  callback = function()
    vim.opt_local.wrap = false
  end,
})

autocmd("FileType", {
  group = augroup("k18_commentstring", { clear = true }),
  pattern = { "kdl", "dotenv" },
  callback = function(event)
    if event.match == "kdl" then
      vim.bo.commentstring = "//%s"
    elseif event.match == "dotenv" then
      vim.bo.commentstring = "#%s"
    end
  end,
})

autocmd({ "BufLeave", "BufWinLeave" }, {
  group = augroup("k18_folds", { clear = true }),
  pattern = "*",
  callback = function()
    pcall(vim.cmd, "silent! mkview")
  end,
  desc = "Remember folds on buffer exit",
})

autocmd("BufReadPost", {
  group = augroup("k18_folds", { clear = false }),
  pattern = "*",
  callback = function()
    pcall(vim.cmd, "silent! loadview")
  end,
  desc = "Restore folds on buffer enter",
})

autocmd("FileType", {
  group = augroup("k18_outline", { clear = true }),
  pattern = "Outline",
  callback = function()
    local win = vim.api.nvim_get_current_win()
    vim.api.nvim_set_option_value("spell", false, { win = win })
  end,
})

autocmd({ "BufEnter" }, {
  group = augroup("k18_tmux_syntax", { clear = true }),
  pattern = { "*.tmux.conf", "tmux.conf" },
  callback = function()
    vim.cmd("syntax on")
  end,
})

autocmd({ "BufLeave" }, {
  group = augroup("k18_tmux_syntax", { clear = false }),
  pattern = { "*.tmux.conf", "tmux.conf" },
  callback = function()
    vim.cmd("syntax off")
  end,
})

autocmd("FileType", {
  group = augroup("k18_json_conceal", { clear = true }),
  pattern = { "json", "jsonc", "json5" },
  callback = function()
    vim.opt_local.conceallevel = 0
  end,
})

autocmd("BufWritePre", {
  group = augroup("k18_auto_create_dir", { clear = true }),
  callback = function(event)
    if event.match:match("^%w%w+:[\\/][\\/]") then
      return
    end
    local file = vim.uv.fs_realpath(event.match) or event.match
    vim.fn.mkdir(vim.fn.fnamemodify(file, ":p:h"), "p")
  end,
})
