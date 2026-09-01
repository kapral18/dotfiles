return {
  {
    "github/copilot.vim",
    version = "*",
    init = function()
      -- Pin the language server to mise's node. The login-keychain item
      -- "copilot-language-server" trusts that binary; a shell whose PATH puts
      -- /opt/homebrew/bin first would otherwise run it under Homebrew node and
      -- trigger a keychain prompt. copilot.vim ignores g:copilot_node_command
      -- in npx mode, and npx/npm exec re-resolve `node` from PATH at every hop
      -- (`#!/usr/bin/env node`), so the shims dir must lead PATH for the whole
      -- chain rather than just the first executable.
      local mise_shims = vim.fn.expand("~/.local/share/mise/shims")
      vim.g.copilot_npx_command = { "/usr/bin/env", "PATH=" .. mise_shims .. ":" .. vim.env.PATH, "npx" }
      vim.g.copilot_node_command = mise_shims .. "/node"
      vim.api.nvim_set_hl(0, "CopilotSuggestion", { fg = "#83a598" })
      vim.api.nvim_set_hl(0, "CopilotAnnotation", { fg = "#03a598" })
    end,
  },
}
