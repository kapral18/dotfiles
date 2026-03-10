local fs_util = require("util.fs")
local sttrp = require("plugins_local_src.send-to-tmux-right-pane")

return {
  dir = fs_util.get_plugin_src_dir(),
  keys = {
    { "<leader>ad", sttrp.send_diagnostics, desc = "Send diagnostics to right Tmux pane" },
    { "<leader>al", sttrp.send_current_line, desc = "Send current line to right Tmux pane" },
    { "<leader>av", sttrp.send_selection, mode = "v", desc = "Send selection to right Tmux pane" },
    { "<leader>ah", sttrp.send_git_hunk, mode = { "n", "v" }, desc = "Send git hunk to right Tmux pane" },
    { "<leader>ag", sttrp.send_git_diff_file, desc = "Send git diff (file) to right Tmux pane" },
  },
}
