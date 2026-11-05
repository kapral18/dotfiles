local fs_util = require("util.fs")
local strp = require("plugins_local_src.send-to-right-pane")

return {
  dir = fs_util.get_plugin_src_dir(),
  keys = {
    { "<leader>ad", strp.send_diagnostics, desc = "Send diagnostics to right pane" },
    { "<leader>al", strp.send_current_line, desc = "Send current line to right pane" },
    { "<leader>av", strp.send_selection, mode = "v", desc = "Send selection to right pane" },
    { "<leader>ah", strp.send_git_hunk, mode = { "n", "v" }, desc = "Send git hunk to right pane" },
    { "<leader>ag", strp.send_git_diff_file, desc = "Send git diff (file) to right pane" },
  },
}
