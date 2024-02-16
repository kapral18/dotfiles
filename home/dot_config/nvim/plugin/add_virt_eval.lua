local function add_virt_text_so_file()
  local cmd_str = ""
  if vim.bo.filetype == "lua" then
    cmd_str = "lua %"
  end

  if vim.bo.filetype == "javascript" then
    cmd_str = "node %"
  end

  if vim.bo.filetype == "typescript" then
    cmd_str = "ts-node %"
  end

  if vim.bo.filetype == "sh" then
    cmd_str = "bash %"
  end

  if vim.bo.filetype == "python" then
    cmd_str = "python %"
  end

  if vim.bo.filetype == "rust" then
    cmd_str = "cargo run"
  end

  if vim.bo.filetype == "go" then
    cmd_str = "go run %"
  end

  if vim.bo.filetype == "awk" then
    cmd_str = "awk -f %"
  end

  local line = vim.fn.line(".") - 1

  local ns_id = vim.api.nvim_create_namespace("k18")
  local bufnr = vim.api.nvim_get_current_buf()

  cmd_str = cmd_str:gsub("%%", vim.fn.expand("%"))

  local output = vim.fn.system(cmd_str):gsub("\n", ""):gsub("%s+", " ")

  local compact_outputs = {}
  for i = 1, #output, 60 do
    table.insert(compact_outputs, output:sub(i, i + 59))
  end

  vim.api.nvim_buf_clear_namespace(bufnr, ns_id, 0, -1)

  local lines = vim.api.nvim_buf_get_lines(bufnr, 0, -1, false)
  for i = 1, #compact_outputs do
    table.insert(lines, "")
  end
  vim.api.nvim_buf_set_lines(bufnr, 0, -1, false, lines)

  for i in ipairs(compact_outputs) do
    vim.api.nvim_buf_set_extmark(
      bufnr,
      ns_id,
      line + i,
      0,
      { virt_text = { {
        compact_outputs[i],
        "DiagnosticOk",
      } } }
    )
  end
end

local function del_virt_text_so_file()
  local ns_id = vim.api.nvim_create_namespace("k18")
  local bufnr = vim.api.nvim_get_current_buf()
  vim.api.nvim_buf_clear_namespace(bufnr, ns_id, 0, -1)
  vim.cmd.write()
end

vim.keymap.set(
  { "n" },
  "<leader>sff",
  add_virt_text_so_file,
  { noremap = true, desc = "Inline virt text of file execution" }
)
vim.keymap.set(
  { "n" },
  "<leader>sfd",
  del_virt_text_so_file,
  { noremap = true, desc = "Delete virt text of file execution" }
)
