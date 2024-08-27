-- Ctrl-C to <Esc>
vim.keymap.set("i", "<C-c>", "<ESC>")

-- free the <leader>l
vim.keymap.del("n", "<leader>l")
vim.keymap.set("n", "<leader>lL", function()
  LazyVim.news.changelog()
end, { desc = "LazyVim Changelog" })
vim.keymap.set("n", "<leader>ll", "<cmd>Lazy<cr>", { desc = "Lazy" })

-- For visual mode
vim.keymap.set("v", "<Tab>", ">gv", { noremap = true })
vim.keymap.set("v", "<S-Tab>", "<gv", { noremap = true })

-- map shift j and shift k to beginning and end of line
vim.keymap.set({ "n", "v" }, "<S-h>", "_", { noremap = true, silent = true, desc = "Go to beginning of line" })
vim.keymap.set({ "n", "v" }, "<S-l>", "$", { noremap = true, silent = true, desc = "Go to end of line" })

-- disable save
vim.keymap.del({ "n", "s", "x" }, "<C-s>")

-- jump 5 lines up and down at a time with shift-j and shift-k
-- move faster with shift
vim.keymap.set({ "n", "v" }, "<A-k>", "10k", { noremap = true, silent = true, desc = "Jump 10 lines up" })
vim.keymap.set({ "n", "v" }, "<A-j>", "10j", { noremap = true, silent = true, desc = "Jump 10 lines down" })
vim.keymap.del("i", "<A-k>")
vim.keymap.del("i", "<A-j>")

-- Move Lines
vim.keymap.set("n", "<C-A-j>", "<cmd>m .+1<cr>==", { desc = "Move Down" })
vim.keymap.set("n", "<C-A-k>", "<cmd>m .-2<cr>==", { desc = "Move Up" })
vim.keymap.set("i", "<C-A-j>", "<esc><cmd>m .+1<cr>==gi", { desc = "Move Down" })
vim.keymap.set("i", "<C-A-k>", "<esc><cmd>m .-2<cr>==gi", { desc = "Move Up" })
vim.keymap.set("v", "<C-A-j>", ":m '>+1<cr>gv=gv", { desc = "Move Down" })
vim.keymap.set("v", "<C-A-k>", ":m '<-2<cr>gv=gv", { desc = "Move Up" })

-- Move In Insert Mode
vim.keymap.set("i", "<A-h>", "<Left>", { desc = "Move left" })
vim.keymap.set("i", "<A-l>", "<Right>", { desc = "Move right" })
vim.keymap.set("i", "<A-j>", "<Down>", { desc = "Move down" })
vim.keymap.set("i", "<A-k>", "<Up>", { desc = "Move up" })

-- Paste on cmd+v
vim.keymap.set("v", "<D-c>", "y", { remap = true })
vim.keymap.set({ "n", "v" }, "<D-v>", '"+p', { remap = true })
vim.keymap.set("i", "<D-v>", "<C-r>+", { remap = true })

-- Delete a word by alt+backspace
vim.keymap.set("i", "<A-BS>", "<C-w>", { noremap = true })

-- Disable default window resize maps to allow visual multi to use them
vim.keymap.del("n", "<C-Up>")
vim.keymap.del("n", "<C-Down>")
vim.keymap.del("n", "<C-Left>")
vim.keymap.del("n", "<C-Right>")
vim.keymap.set({ "n", "t" }, "<C-S-Up>", "<cmd>resize -2<cr>", { desc = "Increase window height" })
vim.keymap.set({ "n", "t" }, "<C-S-Down>", "<cmd>resize +2<cr>", { desc = "Decrease window height" })
vim.keymap.set({ "n", "t" }, "<C-S-Left>", "<cmd>vertical resize +2<cr>", { desc = "Increase window width" })
vim.keymap.set({ "n", "t" }, "<C-S-Right>", "<cmd>vertical resize -2<cr>", { desc = "Decrase window width" })

-- open gd in vsplit
vim.keymap.set("n", "<leader>vd", "<cmd>vsplit | lua vim.lsp.buf.definition()<CR>", { noremap = true, silent = true })

-- Toggle statusline
vim.keymap.set("n", "<leader>uS", function()
  if vim.opt.laststatus:get() == 0 then
    vim.opt.laststatus = 3
  else
    vim.opt.laststatus = 0
  end
end, { desc = "Toggle Statusline" })

-- close and go back to previous window
vim.keymap.set("n", "<leader>wq", "<cmd>wincmd p | q<cr>", { desc = "Close window" })

-- Add a space before the current line
vim.keymap.set(
  "n",
  "[<leader>",
  "O<Esc><Down>",
  { noremap = true, silent = true, desc = "Add space before current line" }
)

-- Add a space after the current line
vim.keymap.set("n", "]<leader>", "o<Esc><Up>", { noremap = true, silent = true, desc = "Add space after current line" })

-- quickfix list delete keymap
function Remove_qf_item()
  local curqfidx = vim.fn.line(".")
  local qfall = vim.fn.getqflist()

  -- Return if there are no items to remove
  if #qfall == 0 then
    return
  end

  -- Remove the item from the quickfix list
  table.remove(qfall, curqfidx)
  vim.fn.setqflist(qfall, "r")

  -- Reopen quickfix window to refresh the list
  vim.cmd("copen")

  -- If not at the end of the list, stay at the same index, otherwise, go one up.
  local new_idx = curqfidx < #qfall and curqfidx or math.max(curqfidx - 1, 1)

  -- Set the cursor position directly in the quickfix window
  local winid = vim.fn.win_getid() -- Get the window ID of the quickfix window
  vim.api.nvim_win_set_cursor(winid, { new_idx, 0 })
end

vim.cmd("command! RemoveQFItem lua Remove_qf_item()")
vim.api.nvim_command("autocmd FileType qf nnoremap <buffer> dd :RemoveQFItem<cr>")

local function switch_between_source_and_test()
  local current_file = vim.fn.expand("%:p")
  local test_file, source_file

  -- Check if the current file is a source file or a test file
  if current_file:match("%.test%.") or current_file:match("%.spec%.") then
    -- It's a test file, find the corresponding source file
    source_file = current_file:gsub("%.test%.", "."):gsub("%.spec%.", ".")
    if vim.fn.filereadable(source_file) == 1 then
      vim.cmd("edit " .. source_file)
    else
      print("Source file not found")
    end
  else
    -- It's a source file, find the corresponding test file
    local base_file = current_file:match("(.*)%.")
    test_file = base_file .. ".test." .. vim.fn.expand("%:e")
    if vim.fn.filereadable(test_file) == 1 then
      vim.cmd("edit " .. test_file)
    else
      test_file = base_file .. ".spec." .. vim.fn.expand("%:e")
      if vim.fn.filereadable(test_file) == 1 then
        vim.cmd("edit " .. test_file)
      else
        print("Test file not found")
      end
    end
  end
end

vim.keymap.set("n", "<C-^>", switch_between_source_and_test, { desc = "Switch between source and test" })
