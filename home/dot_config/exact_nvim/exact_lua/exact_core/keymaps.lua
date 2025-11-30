local util = require("util")

local function map(mode, lhs, rhs, opts)
  opts = opts or {}
  if type(opts) == "string" then
    opts = { desc = opts }
  end
  opts.silent = opts.silent ~= false
  vim.keymap.set(mode, lhs, rhs, opts)
end

map("i", "<C-c>", "<Esc>")
map("i", "jk", "<Esc>")

map({ "n", "x" }, "j", [[v:count == 0 ? 'gj' : 'j']], { expr = true, desc = "Down" })
map({ "n", "x" }, "<Down>", [[v:count == 0 ? 'gj' : 'j']], { expr = true, desc = "Down" })
map({ "n", "x" }, "k", [[v:count == 0 ? 'gk' : 'k']], { expr = true, desc = "Up" })
map({ "n", "x" }, "<Up>", [[v:count == 0 ? 'gk' : 'k']], { expr = true, desc = "Up" })

map("n", "<C-h>", "<C-w>h", { desc = "Go to Left Window", remap = true })
map("n", "<C-j>", "<C-w>j", { desc = "Go to Lower Window", remap = true })
map("n", "<C-k>", "<C-w>k", { desc = "Go to Upper Window", remap = true })
map("n", "<C-l>", "<C-w>l", { desc = "Go to Right Window", remap = true })

-- Window resize with Ctrl-Shift instead of Ctrl (to free Ctrl for visual-multi)
map({ "n", "t" }, "<C-S-Up>", "<cmd>resize -2<cr>", { desc = "Increase window height" })
map({ "n", "t" }, "<C-S-Down>", "<cmd>resize +2<cr>", { desc = "Decrease window height" })
map({ "n", "t" }, "<C-S-Left>", "<cmd>vertical resize +2<cr>", { desc = "Increase window width" })
map({ "n", "t" }, "<C-S-Right>", "<cmd>vertical resize -2<cr>", { desc = "Decrease window width" })

-- Jump 10 lines up and down with Alt-j and Alt-k
map({ "n", "v" }, "<A-k>", "10k", { desc = "Jump 10 lines up" })
map({ "n", "v" }, "<A-j>", "10j", { desc = "Jump 10 lines down" })

-- Move lines with Ctrl-Alt-j and Ctrl-Alt-k
map("n", "<C-A-j>", "<cmd>m .+1<cr>==", { desc = "Move Down" })
map("n", "<C-A-k>", "<cmd>m .-2<cr>==", { desc = "Move Up" })
map("i", "<C-A-j>", "<esc><cmd>m .+1<cr>==gi", { desc = "Move Down" })
map("i", "<C-A-k>", "<esc><cmd>m .-2<cr>==gi", { desc = "Move Up" })
map("v", "<C-A-j>", ":m '>+1<cr>gv=gv", { desc = "Move Down" })
map("v", "<C-A-k>", ":m '<-2<cr>gv=gv", { desc = "Move Up" })

map({ "n", "v" }, "<S-h>", "_", { desc = "Go to beginning of line" })
map({ "n", "v" }, "<S-l>", "$", { desc = "Go to end of line" })

map({ "i", "n", "s" }, "<Esc>", function()
  vim.cmd.nohlsearch()
  util.cmp.actions.snippet_stop()
  return "<Esc>"
end, { expr = true, desc = "Escape and Clear hlsearch" })

map("n", "<leader>ur", "<Cmd>nohlsearch|diffupdate|normal! <C-L><CR>", { desc = "Redraw / Clear hlsearch" })

map("n", "n", "'Nn'[v:searchforward].'zv'", { expr = true, desc = "Next Search Result" })
map("x", "n", "'Nn'[v:searchforward]", { expr = true, desc = "Next Search Result" })
map("o", "n", "'Nn'[v:searchforward]", { expr = true, desc = "Next Search Result" })
map("n", "N", "'nN'[v:searchforward].'zv'", { expr = true, desc = "Prev Search Result" })
map("x", "N", "'nN'[v:searchforward]", { expr = true, desc = "Prev Search Result" })
map("o", "N", "'nN'[v:searchforward]", { expr = true, desc = "Prev Search Result" })

map("i", ",", ",<c-g>u")
map("i", ".", ".<c-g>u")
map("i", ";", ";<c-g>u")

-- Ctrl-s is disabled (was saving, but we prefer manual saves)
map("n", "<leader>K", "<cmd>norm! K<cr>", { desc = "Keywordprg" })

map("x", "<", "<gv")
map("x", ">", ">gv")

map("n", "gco", "o<esc>Vcx<esc><cmd>normal gcc<cr>fxa<bs>", { desc = "Add Comment Below" })
map("n", "gcO", "O<esc>Vcx<esc><cmd>normal gcc<cr>fxa<bs>", { desc = "Add Comment Above" })

map("n", "<leader>fn", "<cmd>enew<cr>", { desc = "New File" })

map("n", "<leader>bb", "<cmd>e #<cr>", { desc = "Switch to Other Buffer" })
map("n", "<leader>`", "<cmd>e #<cr>", { desc = "Switch to Other Buffer" })
map("n", "[b", "<cmd>bprevious<cr>", { desc = "Prev Buffer" })
map("n", "]b", "<cmd>bnext<cr>", { desc = "Next Buffer" })
map("n", "<leader>bD", "<cmd>:bd<cr>", { desc = "Delete Buffer and Window" })

map("n", "<leader>xl", function()
  local ok, err = pcall(vim.fn.getloclist(0, { winid = 0 }).winid ~= 0 and vim.cmd.lclose or vim.cmd.lopen)
  if not ok and err then
    vim.notify(err, vim.log.levels.ERROR)
  end
end, { desc = "Location List" })

map("n", "<leader>xq", function()
  local ok, err = pcall(vim.fn.getqflist({ winid = 0 }).winid ~= 0 and vim.cmd.cclose or vim.cmd.copen)
  if not ok and err then
    vim.notify(err, vim.log.levels.ERROR)
  end
end, { desc = "Quickfix List" })

map("n", "[q", vim.cmd.cprev, { desc = "Previous Quickfix" })
map("n", "]q", vim.cmd.cnext, { desc = "Next Quickfix" })

map({ "n", "x" }, "<leader>cf", function()
  util.format.format({ force = true })
end, { desc = "Format" })

local function diagnostic_goto(next, severity)
  return function()
    vim.diagnostic.jump({
      count = (next and 1 or -1) * vim.v.count1,
      severity = severity and vim.diagnostic.severity[severity] or nil,
      float = true,
    })
  end
end

map("n", "<leader>cd", vim.diagnostic.open_float, { desc = "Line Diagnostics" })
map("n", "]d", diagnostic_goto(true), { desc = "Next Diagnostic" })
map("n", "[d", diagnostic_goto(false), { desc = "Prev Diagnostic" })
map("n", "]e", diagnostic_goto(true, "ERROR"), { desc = "Next Error" })
map("n", "[e", diagnostic_goto(false, "ERROR"), { desc = "Prev Error" })
map("n", "]w", diagnostic_goto(true, "WARN"), { desc = "Next Warning" })
map("n", "[w", diagnostic_goto(false, "WARN"), { desc = "Prev Warning" })

-- Tab management
map("n", "<leader><tab>l", "<cmd>tablast<cr>", { desc = "Last Tab" })
map("n", "<leader><tab>o", "<cmd>tabonly<cr>", { desc = "Close Other Tabs" })
map("n", "<leader><tab>f", "<cmd>tabfirst<cr>", { desc = "First Tab" })
map("n", "<leader><tab><tab>", "<cmd>tabnew<cr>", { desc = "New Tab" })
map("n", "<leader><tab>]", "<cmd>tabnext<cr>", { desc = "Next Tab" })
map("n", "<leader><tab>d", "<cmd>tabclose<cr>", { desc = "Close Tab" })
map("n", "<leader><tab>[", "<cmd>tabprevious<cr>", { desc = "Previous Tab" })

map("n", "<leader>qq", "<cmd>qa<cr>", { desc = "Quit All" })
map("n", "<leader>ui", vim.show_pos, { desc = "Inspect Pos" })
map("n", "<leader>uI", function()
  vim.treesitter.inspect_tree()
  vim.api.nvim_input("I")
end, { desc = "Inspect Tree" })

map("n", "<leader>lL", function()
  util.news.changelog()
end, { desc = "Changelog" })
map("n", "<leader>ll", "<cmd>Lazy<cr>", { desc = "Lazy" })
map("n", "<leader>cm", "<cmd>Mason<cr>", { desc = "Mason" })

map("n", "<leader>-", "<C-W>s", { desc = "Split Window Below", remap = true })
map("n", "<leader>|", "<C-W>v", { desc = "Split Window Right", remap = true })
map("n", "<leader>wd", "<C-W>c", { desc = "Delete Window", remap = true })

map("v", "<Tab>", ">gv")
map("v", "<S-Tab>", "<gv")

map("i", "<A-h>", "<Left>", { desc = "Move left" })
map("i", "<A-l>", "<Right>", { desc = "Move right" })
map("i", "<A-j>", "<Down>", { desc = "Move down" })
map("i", "<A-k>", "<Up>", { desc = "Move up" })

map("v", "<D-c>", "y", { remap = true })
map({ "n", "v" }, "<D-v>", '"+p', { remap = true })
map("i", "<D-v>", "<C-r>+", { remap = true })
map("i", "<A-BS>", "<C-w>")

map("n", "<leader>gb", "<cmd>BlameToggle<cr>", { desc = "Blame" })
map("n", "<leader>vd", "<cmd>vsplit | lua vim.lsp.buf.definition()<CR>", { desc = "LSP Definition (split)" })

map("n", "<leader>uS", function()
  vim.opt.laststatus = vim.opt.laststatus:get() == 0 and 3 or 0
end, { desc = "Toggle Statusline" })

map("n", "<leader>wq", "<cmd>wincmd p | q<cr>", { desc = "Close window" })

vim.api.nvim_create_user_command("LargeFiles", function(opts)
  local args = vim.split(opts.args or "", " ")
  local min_lines = tonumber(args[1]) or 5000
  local max_lines = tonumber(args[2])

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

  local filtered_lines = {}
  for _, line in ipairs(vim.split(output, "\n")) do
    if line ~= "" then
      local file_path = line:match("(.-):1:")
      if file_path and not util.is_image(file_path) then
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
  vim.cmd.copen()
end, { desc = "List files exceeding N lines", nargs = "*" })

vim.api.nvim_create_user_command("CpFromDownloads", function()
  if vim.bo.filetype ~= "neo-tree" then
    print("This command should be used in a Neo-tree buffer")
    return
  end

  local state = require("neo-tree.sources.manager").get_state("filesystem")
  if not state then
    print("Unable to get Neo-tree state")
    return
  end

  local node = state.tree:get_node()
  if not node then
    print("No node selected")
    return
  end

  local path = node:get_id()
  if vim.fn.isdirectory(path) ~= 1 then
    path = vim.fn.fnamemodify(path, ":h")
  end

  local cmd = string.format("!cp ~/Downloads/ %s/", vim.fn.fnameescape(path))
  vim.cmd('call feedkeys(":' .. cmd .. '\\<C-Left>\\<Left>", "n")')
end, { desc = "Copy from ~/Downloads into selected Neo-tree directory" })

vim.api.nvim_create_autocmd("FileType", {
  group = vim.api.nvim_create_augroup("k18_keymaps", { clear = true }),
  pattern = "neo-tree",
  callback = function()
    map("n", "<leader>cp", "<cmd>CpFromDownloads<cr>", { buffer = true, desc = "Copy from Downloads" })
  end,
})

vim.api.nvim_create_user_command("WW", function()
  vim.cmd("noautocmd write")
end, { desc = "Write without autocmds" })

vim.api.nvim_create_user_command("WWW", function()
  vim.cmd("noautocmd Wall")
end, { desc = "Write all without autocmds" })

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
        print("Failed to create tags")
      end
    end,
  })
end, { desc = "Generate ctags respecting .gitignore" })

map("n", "<leader>mt", "<cmd>MakeTags<cr>", { desc = "Make Tags" })

map("n", "<leader>yp", function()
  local cur_file = vim.fn.fnamemodify(vim.api.nvim_buf_get_name(0), ":~:.")
  if cur_file == "" then
    return
  end
  util.copy_to_clipboard(cur_file)
  vim.notify(("Copied %s to clipboard"):format(cur_file), vim.log.levels.INFO, { title = "Path Copied" })
end, { desc = "Copy current file relative path" })

map("n", "<leader>yP", function()
  local cur_file = vim.fn.fnamemodify(vim.api.nvim_buf_get_name(0), ":p")
  if cur_file == "" then
    return
  end
  util.copy_to_clipboard(cur_file)
  vim.notify(("Copied %s to clipboard"):format(cur_file), vim.log.levels.INFO, { title = "Absolute Path Copied" })
end, { desc = "Copy current file absolute path" })

map("n", "<leader>ad", function()
  local file_path = vim.api.nvim_buf_get_name(0)
  local diagnostics = vim.diagnostic.get(0)

  if #diagnostics == 0 then
    vim.notify("No diagnostics found", vim.log.levels.INFO)
    return
  end

  local diag_lines = {}
  for _, d in ipairs(diagnostics) do
    local severity = vim.diagnostic.severity[d.severity] or "UNKNOWN"
    table.insert(diag_lines, string.format("Line %d: [%s] %s", d.lnum + 1, severity, d.message))
  end

  local message =
    string.format("Here are the diagnostics for file `%s`:\n\n```\n%s\n```", file_path, table.concat(diag_lines, "\n"))

  local tmp_file = os.tmpname()
  local f = io.open(tmp_file, "w")
  if f then
    f:write(message)
    f:close()
  end

  local current_pane = vim.fn.system("tmux display-message -p '#{pane_id}'"):gsub("%s+", "")
  local target_pane = vim.fn
    .system(
      string.format(
        "tmux select-pane -R -t %s \\; display-message -p '#{pane_id}' \\; select-pane -t %s",
        current_pane,
        current_pane
      )
    )
    :gsub("%s+", "")

  if target_pane == "" or target_pane == current_pane then
    vim.notify("No pane to the right found", vim.log.levels.WARN)
    os.remove(tmp_file)
    return
  end

  vim.fn.system(string.format("tmux load-buffer %s", tmp_file))
  vim.fn.system(string.format("tmux paste-buffer -t %s", target_pane))

  os.remove(tmp_file)
  vim.notify("Diagnostics sent to right pane", vim.log.levels.INFO)
end, { desc = "Send diagnostics to right Tmux pane" })
