local augroup = vim.api.nvim_create_augroup
local autocmd = vim.api.nvim_create_autocmd

local ui = require("util.ui")
if ui.config and ui.config.icons and ui.config.icons.diagnostics then
  local icons = ui.config.icons.diagnostics
  for name, icon in pairs(icons) do
    local hl = "DiagnosticSign" .. name
    vim.fn.sign_define(hl, { text = icon, texthl = hl, numhl = "" })
  end
end

local general = augroup("k18_general", { clear = true })
local hashed_undo_dir = vim.fn.stdpath("state") .. "/undo-hashed"
vim.fn.mkdir(hashed_undo_dir, "p")

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

local function hashed_undo_file_path(bufnr)
  local abs_path = vim.api.nvim_buf_get_name(bufnr)
  if abs_path == "" then
    return nil
  end

  local real_path = vim.uv.fs_realpath(abs_path) or abs_path
  local base = vim.fn.fnamemodify(real_path, ":t"):gsub("[^%w%._%-]", "_")
  local hash = vim.fn.sha256(real_path):sub(1, 16)
  return string.format("%s/%s-%s.undo", hashed_undo_dir, base, hash)
end

autocmd("BufReadPost", {
  group = augroup("k18_hashed_undo", { clear = true }),
  callback = function(event)
    if vim.bo[event.buf].buftype ~= "" then
      return
    end

    local undofile = hashed_undo_file_path(event.buf)
    if not undofile or vim.fn.filereadable(undofile) ~= 1 then
      return
    end

    pcall(vim.cmd, "silent! rundo " .. vim.fn.fnameescape(undofile))
  end,
})

autocmd("BufWritePost", {
  group = augroup("k18_hashed_undo", { clear = false }),
  callback = function(event)
    if vim.bo[event.buf].buftype ~= "" then
      return
    end

    local undofile = hashed_undo_file_path(event.buf)
    if not undofile then
      return
    end

    vim.fn.mkdir(vim.fn.fnamemodify(undofile, ":h"), "p")
    pcall(vim.cmd, "silent! wundo " .. vim.fn.fnameescape(undofile))
  end,
})

vim.api.nvim_create_user_command("UndoHashedPrune", function(opts)
  local args = vim.split(opts.args or "", "%s+", { trimempty = true })
  local max_age_days = tonumber(args[1]) or 30
  local max_total_mb = tonumber(args[2]) or 512

  local max_age_sec = math.max(0, max_age_days) * 24 * 60 * 60
  local max_total_bytes = math.max(0, max_total_mb) * 1024 * 1024
  local now = os.time()

  local entries = {}
  local total_bytes = 0

  local dir_obj = vim.uv.fs_scandir(hashed_undo_dir)
  if not dir_obj then
    vim.notify("UndoHashedPrune: cannot scan " .. hashed_undo_dir, vim.log.levels.WARN)
    return
  end

  while true do
    local name, t = vim.uv.fs_scandir_next(dir_obj)
    if not name then
      break
    end
    if t == "file" and name:match("%.undo$") then
      local full = hashed_undo_dir .. "/" .. name
      local stat = vim.uv.fs_stat(full)
      if stat then
        local mtime = stat.mtime and stat.mtime.sec or 0
        local size = stat.size or 0
        total_bytes = total_bytes + size
        table.insert(entries, { path = full, mtime = mtime, size = size })
      end
    end
  end

  table.sort(entries, function(a, b)
    return a.mtime < b.mtime
  end)

  local deleted = 0
  local deleted_bytes = 0

  for _, e in ipairs(entries) do
    if max_age_sec > 0 and (now - e.mtime) > max_age_sec then
      if vim.fn.delete(e.path) == 0 then
        deleted = deleted + 1
        deleted_bytes = deleted_bytes + e.size
        total_bytes = total_bytes - e.size
      end
    end
  end

  if max_total_bytes > 0 and total_bytes > max_total_bytes then
    for _, e in ipairs(entries) do
      if vim.uv.fs_stat(e.path) and total_bytes > max_total_bytes then
        if vim.fn.delete(e.path) == 0 then
          deleted = deleted + 1
          deleted_bytes = deleted_bytes + e.size
          total_bytes = total_bytes - e.size
        end
      end
    end
  end

  vim.notify(
    string.format(
      "UndoHashedPrune: deleted %d file(s), freed %.1fMB",
      deleted,
      deleted_bytes / (1024 * 1024)
    ),
    vim.log.levels.INFO
  )
end, {
  nargs = "*",
  desc = "Prune hashed undo files: :UndoHashedPrune [max_age_days] [max_total_mb]",
})
