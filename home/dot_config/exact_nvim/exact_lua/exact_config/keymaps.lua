-- Ctrl-C to <Esc>
vim.keymap.set("i", "<C-c>", "<ESC>")
vim.keymap.set("i", "jk", "<ESC>")

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

-- Remove snacks blame
vim.keymap.del("n", "<leader>gb")
vim.keymap.set("n", "<leader>gb", function()
  vim.cmd("BlameToggle")
end, { desc = "Blame" })

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

vim.api.nvim_create_user_command("LargeFiles", function(opts)
  local args = vim.split(opts.args or "", " ")
  local min_lines = tonumber(args[1]) or 5000
  local max_lines = tonumber(args[2])
  local common_utils = require("utils.common")

  local cmd = string.format(
    [[git ls-files -z | xargs -0 wc -l | grep -v total | awk '$1 > %d %s { print $2 ":1:" $1 " lines" }']],
    min_lines,
    max_lines and string.format("&& $1 < %d", max_lines) or ""
  )
  local output = vim.fn.system(cmd)

  if output == "" then
    print(string.format("No files found in specified range of %d-%s lines", min_lines, max_lines or "∞"))
    return
  end

  -- Filter out image files
  local filtered_lines = {}
  for _, line in ipairs(vim.split(output, "\n")) do
    if line ~= "" then
      local file_path = line:match("(.-):1:")
      if file_path and not common_utils.is_image(file_path) then
        table.insert(filtered_lines, line)
      end
    end
  end

  if #filtered_lines == 0 then
    print(string.format("No non-image files found in specified range of %d-%s lines", min_lines, max_lines or "∞"))
    return
  end

  vim.fn.setqflist({}, " ", {
    title = string.format("Large Files (%d-%s lines)", min_lines, max_lines and tostring(max_lines) or "∞"),
    lines = filtered_lines,
  })
  vim.cmd("copen")
end, {
  desc = "List non-image files with lines between N and M (both optional). Default is 5000 lines",
  nargs = "*",
})

-- Copy from Downloads
-- This commands constructs a cp command to copy files from the ~/Downloads directory to the currently
-- selected directory in Neo-tree. It opens the command-line with the constructed command -- cp ~/Downloads/ <selected_directory>
-- and positions the cursor at the end of the ~/Downloads/ part so that you can type the rest of the command.
vim.api.nvim_create_user_command("CpFromDownloads", function()
  -- Check if we're in a Neo-tree buffer
  if vim.bo.filetype ~= "neo-tree" then
    print("This command should be used in a Neo-tree buffer")
    return
  end

  -- Get the current Neo-tree state
  local state = require("neo-tree.sources.manager").get_state("filesystem")
  if not state then
    print("Unable to get Neo-tree state")
    return
  end

  -- Get the currently selected node
  local node = state.tree:get_node()
  if not node then
    print("No node selected")
    return
  end

  -- Get the full path of the selected node
  local path = node:get_id()
  if vim.fn.isdirectory(path) ~= 1 then
    -- If it's a file, get its parent directory
    path = vim.fn.fnamemodify(path, ":h")
  end

  -- Construct the command
  local cmd = string.format("!cp ~/Downloads/ %s/", vim.fn.fnameescape(path))

  -- Open command-line with the constructed command and position cursor
  vim.cmd('call feedkeys(":' .. cmd .. '\\<C-Left>\\<Left>", "n")')
end, {
  desc = "Construct a cp command to copy files from ~/Downloads to the selected directory",
})

-- Add keymap for filetype neo-tree only
vim.api.nvim_create_autocmd("FileType", {
  group = "k18",
  pattern = "neo-tree",
  callback = function()
    vim.keymap.set("n", "<leader>cp", "<cmd>CpFromDownloads<cr>", { buffer = true, desc = "Copy from Downloads" })
  end,
})

-- user command to noautocmd write
vim.api.nvim_create_user_command("WW", function()
  vim.cmd("noautocmd write")
end, {
  desc = "Write without triggering autocommands",
})

-- user command to noautocmd write all
vim.api.nvim_create_user_command("WWW", function()
  vim.cmd("noautocmd Wall")
end, {
  desc = "Write all without triggering autocommands",
})

vim.api.nvim_create_user_command("MakeTags", function()
  local cmd = [[
    if [ -f .gitignore ]; then sed "s/\///" .gitignore > .ctagsignore; fi
    ctags -R --exclude=@.ctagsignore .
  ]]
  vim.fn.jobstart({ "bash", "-c", cmd }, {
    on_exit = function(_, exit_code)
      if exit_code == 0 then
        print("Tags created successfully")
      else
        print(exit_code)
        print("Error creating tags")
      end
    end,
    stdout_buffered = true,
    stderr_buffered = true,
  })
end, {
  desc = "Create tags for the project",
})

vim.keymap.set("n", "<leader>mt", "<cmd>MakeTags<cr>", { desc = "Make Tags" })
