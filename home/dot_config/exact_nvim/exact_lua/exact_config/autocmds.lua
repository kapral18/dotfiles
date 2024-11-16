local augrp = vim.api.nvim_create_augroup
local aucmd = vim.api.nvim_create_autocmd

augrp("k18", {})

-- Autocmds are automatically loaded on the VeryLazy event
-- Default autocmds that are always set: https://github.com/LazyVim/LazyVim/blob/main/lua/lazyvim/config/autocmds.lua
-- Add any additional autocmds here
aucmd({ "FileType" }, {
  group = "k18",
  pattern = { "markdown" },
  callback = function()
    vim.wo.spell = true
  end,
})

aucmd({ "FileType" }, {
  group = "k18",
  pattern = { "kdl" },
  callback = function()
    vim.bo.commentstring = "//%s"
  end,
})

aucmd({ "FileType" }, {
  group = "k18",
  pattern = { "dotenv" },
  callback = function()
    vim.bo.commentstring = "#%s"
  end,
})

-- Enable syntax highlighting for tmux configuration files when entering
aucmd("BufEnter", {
  group = "k18",
  pattern = { "*.tmux.conf", "tmux.conf" },
  command = "syntax on",
})

-- Disable syntax highlighting for tmux configuration files when leaving
aucmd("BufLeave", {
  group = "k18",
  pattern = { "*.tmux.conf", "tmux.conf" },
  command = "syntax off",
})

--persist folds
aucmd({ "BufLeave", "BufWinLeave" }, {
  group = "k18",
  pattern = "*",
  callback = function()
    vim.cmd([[silent! mkview]])
  end,
  desc = "Remember folds on buffer exit",
})

aucmd("BufReadPost", {
  group = "k18",
  pattern = "*",
  callback = function()
    vim.cmd([[silent! loadview]])
  end,
  desc = "Restore folds on buffer enter",
})

-- extract close_qith_q patterns from lazyvim_close_with_q autocmd group
-- and set them to ouse own autocmd group and then delete the lazyvim_close_with_q group
local close_with_q = vim.api.nvim_get_autocmds({ group = "lazyvim_close_with_q", event = "FileType" })

local M = {}
for _, autocmd in ipairs(close_with_q) do
  if autocmd.event == "FileType" then
    table.insert(M, autocmd.pattern)
  end
end

vim.api.nvim_del_augroup_by_name("lazyvim_close_with_q")

aucmd("FileType", {
  group = "k18",
  -- merge patterns with the new ones
  pattern = vim
    .iter({
      M,
      "aerial-nav",
      "chatpgpt",
      "diagmsg",
      "fzf",
      "neotest-output",
      "dap-float",
      "dap-repl",
      "scratch",
    })
    :flatten(math.huge)
    :totable(),
  callback = function(event)
    vim.bo[event.buf].buflisted = false
    vim.keymap.set("n", "q", "<cmd>close<CR>", { buffer = event.buf, silent = true })
  end,
})

aucmd("FileType", {
  group = "k18",
  -- merge patterns with the new ones
  pattern = "Outline",
  callback = function()
    -- no spell
    local cur_win = vim.api.nvim_get_current_win()
    vim.api.nvim_set_option_value("spell", false, { win = cur_win })
  end,
})

vim.api.nvim_create_user_command("LargeFiles", function()
  local cmd = [[git ls-files -z | xargs -0 wc -l | grep -v total | awk '$1 > 5000 { print $2 ":1:" $1 " lines" }']]
  local output = vim.fn.system(cmd)
  vim.fn.setqflist({}, " ", {
    title = "Large Files (>5000 lines)",
    lines = vim.split(output, "\n"),
  })
  vim.cmd("copen")
end, {
  desc = "List files with more than 5000 lines in quickfix",
})
