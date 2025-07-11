local M = {}

-- function to save/append(if file exists) current buffer content to a file
-- for AI consumption in the format of:
-- ---------------------------------------------
-- #FILE: <relative filename from current directory>
-- ---------------------------------------------
-- <file content>
-- ---------------------------------------------
-- <intentional newline>
--
-- There will be 2 keymaps for this command:
-- <leader>cc to save the current buffer to ~/ai_data.txt. Every new invocation will append that file.
--
-- <leader>cC to save the current buffer to ~/ai_data.txt, but it will replace the file content.

function M.save_buffer_to_ai_file(append)
  local output_path = vim.fn.expand("~/ai_data.txt")
  local relative_file_name = vim.fn.fnamemodify(vim.fn.expand("%:p"), ":.")
  local file_content = vim.api.nvim_buf_get_lines(0, 0, -1, false)

  local content = string.format(
    "\n---------------------------------------------\n"
      .. "#FILE: %s"
      .. "\n---------------------------------------------\n"
      .. "%s"
      .. "\n---------------------------------------------\n"
      .. "\n",
    relative_file_name,
    table.concat(file_content, "\n")
  )

  -- Check for duplicates if appending
  if append and vim.fn.filereadable(output_path) == 1 then
    local existing_content = vim.fn.readfile(output_path)
    local existing_text = table.concat(existing_content, "\n")

    -- Check if this file entry already exists
    local file_pattern = string.format("#FILE: %s\n", vim.pesc(relative_file_name))
    if existing_text:match(file_pattern) then
      print("File already exists in " .. output_path .. ". Skipping to prevent duplicate.")
      return
    end
  end

  local mode = append and "a" or "w"
  local file = io.open(output_path, mode)
  if file then
    file:write(content)
    file:close()
    print("Buffer content saved to " .. output_path)
  else
    print("Error: Could not open file " .. output_path)
  end
end

return M
