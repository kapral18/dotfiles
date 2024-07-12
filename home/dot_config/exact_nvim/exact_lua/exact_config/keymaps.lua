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
vim.keymap.set({ "n", "v" }, "<S-M-j>", "10j", { noremap = true, silent = true, desc = "Jump 5 lines down" })
vim.keymap.set({ "n", "v" }, "<S-M-k>", "10k", { noremap = true, silent = true, desc = "Jump 5 lines up" })

-- Remap Ctrl-^ to switch between alternate test and source files
vim.keymap.set(
  "n",
  "<C-^>",
  ":call SwitchSrcTestFile()<CR>",
  { noremap = true, silent = true, desc = "Switch Src/Test File" }
)

-- Paste on cmd+v
vim.keymap.set("v", "<D-c>", "y", { remap = true })
vim.keymap.set({ "n", "v" }, "<D-v>", '"+p', { remap = true })
vim.keymap.set("i", "<D-v>", "<C-r>+", { remap = true })

-- Delete a word by alt+backspace
vim.keymap.set("i", "<A-BS>", "<C-w>", { noremap = true })

vim.api.nvim_exec2(
  [[
  function! SwitchSrcTestFile()
    let current_file = expand("%")
    let alternate_file = substitute(
      \ current_file,
      \ '\v(\w+)(\.spec|\.test)?(\.\w+)$',
      \ '\=submatch(1) . (empty(submatch(2)) ? GetFileExtension() : "") . submatch(3)',
      \ ""
    \)
    if alternate_file != "" 
      execute "e " . alternate_file
    else
      normal! <C-^>
    endif
  endfunction

  function! GetFileExtension()
    if filereadable(resolve(expand("%:.:h") . "/" . submatch(1) . ".spec" . submatch(3)))
      return ".spec"
    elseif filereadable(resolve(expand("%:.:h") . "/" . submatch(1) . ".test" . submatch(3)))
      return ".test"
    else
      return ""
    endif
  endfunction
  ]],
  {}
)

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

-- Set up key mappings for the scratch buffer
local function setup_keymaps()
  local opts = { buffer = true }
  vim.keymap.set("n", "<C-c>", ":q<CR>", opts) -- Ctrl-C to close
  vim.keymap.set("n", "q", ":q<CR>", opts) -- q to close
  vim.keymap.set("n", "<Esc>", ":q<CR>", opts) -- Esc to close
end
-- Create a new scratch buffer
vim.keymap.set("n", "<leader>ws", function()
  local buf = vim.api.nvim_create_buf(false, true)
  vim.api.nvim_set_option_value("buftype", "nofile", { buf = buf })
  vim.api.nvim_set_option_value("bufhidden", "hide", { buf = buf })
  vim.api.nvim_set_option_value("swapfile", false, { buf = buf })

  local width = vim.api.nvim_get_option_value("columns", {})
  local height = vim.api.nvim_get_option_value("lines", {})
  local win_height = math.ceil(height * 0.8 - 4)
  local win_width = math.ceil(width * 0.8)
  local row = math.ceil((height - win_height) / 2 - 1)
  local col = math.ceil((width - win_width) / 2)

  local opts = {
    style = "minimal",
    relative = "editor",
    width = win_width,
    height = win_height,
    row = row,
    col = col,
  }

  vim.api.nvim_open_win(buf, true, opts)
  -- Set up key maps for the scratch buffer when it is created
  setup_keymaps()
end, { desc = "Scratch buffer" })

-- Add a space before the current line
vim.keymap.set(
  "n",
  "[<leader>",
  "O<Esc><Down>",
  { noremap = true, silent = true, desc = "Add space before current line" }
)

-- Add a space after the current line
vim.keymap.set("n", "]<leader>", "o<Esc><Up>", { noremap = true, silent = true, desc = "Add space after current line" })

-- Remove quickfix item
vim.cmd([[
  function! RemoveQFItem()
    let curqfidx = line('.') - 1
    let qfall = getqflist()
    call remove(qfall, curqfidx)
    call setqflist(qfall, 'r')
    execute curqfidx + 1 . "cfirst"
    :copen
  endfunction
  :command! RemoveQFItem :call RemoveQFItem()
  autocmd FileType qf map <buffer> dd :RemoveQFItem<CR>
]])
