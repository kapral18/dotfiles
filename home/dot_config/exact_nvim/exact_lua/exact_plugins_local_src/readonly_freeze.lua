local M = {}

local output_dir = vim.fn.expand("~/Downloads/screenshots")
local default_config = "base"
local default_theme = "pigments"

function M.freeze(line1, line2)
  local bufname = vim.api.nvim_buf_get_name(0)
  if bufname == "" then
    vim.notify("freeze: buffer has no file", vim.log.levels.ERROR)
    return
  end

  vim.fn.mkdir(output_dir, "p")
  local output = output_dir .. "/freeze.png"

  local args = {
    "freeze",
    "--output",
    output,
    "--language",
    vim.bo.filetype,
    "--lines",
    line1 .. "," .. line2,
    "--config",
    default_config,
    "--theme",
    default_theme,
    bufname,
  }

  vim.system(args, { text = true }, function(result)
    vim.schedule(function()
      if result.code ~= 0 then
        vim.notify("freeze failed: " .. (result.stderr or ""), vim.log.levels.ERROR)
        return
      end
      -- Copy PNG to clipboard (macOS)
      vim.system({
        "osascript",
        "-e",
        'set the clipboard to (read (POSIX file "' .. output .. '") as «class PNGf»)',
      })
      -- Open the file
      vim.ui.open(output)
      vim.notify("freeze: " .. output)
    end)
  end)
end

return M
