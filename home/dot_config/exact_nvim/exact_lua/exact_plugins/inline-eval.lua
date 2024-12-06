local config_path = vim.fn.stdpath("config")

return {
  dir = config_path .. "/lua/plugins-local",
  keys = {
    {
      "<leader>sff",
      function()
        require("plugins-local.inline-eval").add_virt_text_to_file()
      end,
      desc = "Inline virt text of file execution",
    },
    {
      "<leader>sfd",
      function()
        require("plugins-local.inline-eval").del_virt_text_from_file()
      end,
      desc = "Delete virt text of file execution",
    },
  },
}
