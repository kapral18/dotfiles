require("core.options")

local plugin_modules = {
  "plugins.ai",
  "plugins.bash",
  "plugins.bufferline",
  "plugins.chezmoi",
  "plugins.colorscheme",
  "plugins.completion",
  "plugins.core",
  "plugins.dap",
  "plugins.diff",
  "plugins.docker",
  "plugins.eslint",
  "plugins.fish",
  "plugins.formatting",
  "plugins.fzf",
  "plugins.git",
  "plugins.github",
  "plugins.go",
  "plugins.gx",
  "plugins.helm",
  "plugins.highlight",
  "plugins.hlargs",
  "plugins.html-css",
  "plugins.inc-rename",
  "plugins.jinja",
  "plugins.json",
  "plugins.jsonl",
  "plugins.kdl",
  "plugins.lazydev",
  "plugins.leap",
  "plugins.lint",
  "plugins.live-command",
  "plugins.lsp",
  "plugins.lua",
  "plugins.lualine",
  "plugins.markdown",
  "plugins.marks",
  "plugins.multi-cursors",
  "plugins.neo-tree",
  "plugins.numb",
  "plugins.osv",
  "plugins.outline",
  "plugins.dash-paq",
  "plugins.python",
  "plugins.rust",
  "plugins.search-and-replace",
  "plugins.session",
  "plugins.snacks",
  "plugins.strudel",
  "plugins.telescope",
  "plugins.tpope",
  "plugins.treesitter",
  "plugins.typescript-tools",
  "plugins.undo",
  "plugins.which-key",
  "plugins.xml",
  "plugins.yaml",
}

local local_modules = {
  "plugins_local.copy-to-qf",
  "plugins_local.freeze",
  "plugins_local.lsp-progress",
  "plugins_local.owner-code-search",
  "plugins_local.qf",
  "plugins_local.run-jest-in-split",
  "plugins_local.send-to-tmux-right-pane",
  "plugins_local.show-file-owner",
  "plugins_local.summarize-commit",
  "plugins_local.switch-src-test",
  "plugins_local.toggle-win-width",
  "plugins_local.ts-move-exports",
  "plugins_local.format-md",
  "plugins_local.winbar",
}

local all_modules = {}
vim.list_extend(all_modules, plugin_modules)
vim.list_extend(all_modules, local_modules)

-- dash-paq.nvim loads every plugin, itself included ("plugins.dash-paq"), so
-- it must be on 'runtimepath' before its own setup() runs. dev.json is the
-- checkout choice its dashboard `L` key and `:DashPaq toggle-dev` save.
do
  local default_dir = vim.fn.expand("~/code/dash-paq.nvim/main")
  local function is_checkout(dir)
    return vim.fn.filereadable(vim.fs.joinpath(dir, "lua", "dash_paq", "init.lua")) == 1
  end

  local ok, saved = pcall(function()
    local dev_json = vim.fs.joinpath(vim.fn.stdpath("state"), "dash-paq", "dev.json")
    return vim.json.decode(table.concat(vim.fn.readfile(dev_json), "\n"))
  end)
  local dev_dir = default_dir
  if ok and type(saved) == "table" and saved["dash-paq.nvim"] ~= nil then
    dev_dir = saved["dash-paq.nvim"]
  end

  local use_dev = type(dev_dir) == "string" and dev_dir ~= "" and dev_dir ~= "upstream"
  if use_dev and not is_checkout(dev_dir) then
    if vim.fn.isdirectory(dev_dir) == 1 then
      vim.notify(dev_dir .. " is not a dash-paq.nvim checkout, using upstream", vim.log.levels.WARN)
    end
    use_dev = false
  end

  if use_dev then
    vim.opt.rtp:prepend(dev_dir)
  else
    -- `vim.pack.add` raises when the clone fails (offline, no GitHub auth).
    local ok_add, add_err = pcall(vim.pack.add, { "https://github.com/kapral18/dash-paq.nvim" }, { confirm = false })
    if not ok_add then
      vim.notify("dash-paq.nvim upstream install failed: " .. tostring(add_err), vim.log.levels.WARN)
    end
    -- Without the plugin the whole config fails, so try the local checkout.
    if #vim.api.nvim_get_runtime_file("lua/dash_paq/init.lua", false) == 0 and is_checkout(default_dir) then
      vim.notify("upstream dash-paq.nvim has no lua/dash_paq; using " .. default_dir, vim.log.levels.WARN)
      vim.opt.rtp:prepend(default_dir)
    end
  end
end

require("dash_paq").setup({ modules = all_modules })

require("core.autocmds")
require("core.keymaps")
