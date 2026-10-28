local root = assert(vim.env.PREVIEW_TEST_ROOT)
local scratch = assert(vim.env.PREVIEW_TEST_TMP)
local specs = dofile(root .. "/home/dot_config/exact_nvim/exact_lua/exact_plugins/readonly_markdown.lua")
local preview
for _, spec in ipairs(specs) do
  if spec[1] == "iamcco/markdown-preview.nvim" then
    preview = spec
  end
end
assert(preview, "preview plugin must be configured")

-- mkdp#util#get_platform() supplies the suffix used by mkdp#rpc#start_server().
-- Only the platform lookup is stubbed; the real config executes a local installer.
vim.fn["mkdp#util#get_platform"] = function()
  return "test"
end
local plugin = { dir = scratch .. "/prévïew plugin" }
vim.fn.mkdir(plugin.dir .. "/app", "p")
vim.fn.writefile({ '{"version":"0.0.10"}' }, plugin.dir .. "/package.json")
local binary = plugin.dir .. "/app/bin/markdown-preview-test"
local function installer(lines)
  vim.fn.writefile(lines, plugin.dir .. "/app/install.sh")
end
local tests = {}

function tests.repair()
  installer({
    'printf "%s\\n" "$1" >> installs',
    "mkdir -p bin",
    "printf '#!/bin/sh\\necho %s\\n' \"${1#v}\" > bin/markdown-preview-test",
    "chmod +x bin/markdown-preview-test",
  })
  local cwd = vim.fn.getcwd()
  preview.config(plugin)
  assert(vim.fn.executable(binary) == 1, "loading an existing clone must install missing preview assets")
  assert(vim.fn.getcwd() == cwd, "installing must preserve the editor working directory")
  preview.build(plugin)
  preview.config(plugin)
  assert(
    vim.deep_equal(vim.fn.readfile(plugin.dir .. "/app/installs"), { "v0.0.10" }),
    "config then build must install once"
  )
  vim.fn.delete(binary)
  preview.config(plugin)
  vim.fn.writefile({ '{"version":"0.0.11"}' }, plugin.dir .. "/package.json")
  local link = scratch .. "/plugin link"
  assert(vim.uv.fs_symlink(plugin.dir, link))
  preview.build({ dir = link })
  assert(vim.fn.executable(binary) == 1, "repair and update must leave an executable binary")
  assert(vim.deep_equal(vim.fn.readfile(plugin.dir .. "/app/installs"), { "v0.0.10", "v0.0.10", "v0.0.11" }))
  assert(vim.fn.getcwd() == cwd)
end

function tests.failure()
  installer({ "echo 'download failed' >&2", "exit 23" })
  local ok, err = pcall(preview.config, plugin)
  assert(not ok and tostring(err):find("download failed", 1, true), "report installer stderr")
end

function tests.missing()
  installer({ "echo 'Binary not available for now'", "exit 0" })
  local ok, err = pcall(preview.config, plugin)
  assert(not ok and tostring(err):find("Binary not available", 1, true), "exit zero does not prove assets exist")
end

function tests.signal()
  vim.fn.mkdir(plugin.dir .. "/app/bin", "p")
  vim.fn.writefile({ "#!/bin/sh", "echo 0.0.9" }, binary)
  vim.fn.setfperm(binary, "rwxr-xr-x")
  -- GNU timeout owns this installer's parent process and process group.
  -- Killing that owned process reproduces the signal-only timeout result.
  installer({ 'kill -KILL "$PPID"' })
  local ok, err = pcall(preview.build, plugin)
  assert(not ok and tostring(err):find("signal 9", 1, true), "a killed update must not accept the old binary")
end

function tests.stale()
  vim.fn.mkdir(plugin.dir .. "/app/bin", "p")
  vim.fn.writefile({ "#!/bin/sh", "echo 0.0.9" }, binary)
  vim.fn.setfperm(binary, "rwxr-xr-x")
  installer({ "echo 'Binary not available for now'", "exit 0" })
  local ok, err = pcall(preview.build, plugin)
  assert(
    not ok and tostring(err):find("Binary not available", 1, true),
    "a failed update must not accept the old version"
  )
end

assert(tests[arg[1]], "unknown test case")()
print("PASS " .. arg[1])
