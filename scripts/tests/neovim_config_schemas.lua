local root = assert(vim.env.CONFIG_SCHEMA_TEST_ROOT)
local scratch = assert(vim.uv.fs_realpath(assert(vim.env.CONFIG_SCHEMA_TEST_TMP)))
local lua_root = root .. "/home/dot_config/exact_nvim/exact_lua/"
-- Resolve chezmoi source modules without deploying or loading the user's init.
table.insert(package.loaders, 1, function(name)
  local dir, file = name:match("^([^.]+)%.([^.]+)$")
  if dir then
    local path = lua_root .. "exact_" .. dir .. "/readonly_" .. file .. ".lua"
    if vim.uv.fs_stat(path) then
      return assert(loadfile(path))
    end
  end
end)

local catalog =
  { { name = "package.json", url = "https://www.schemastore.org/package.json", fileMatch = { "package.json" } } }
package.preload.schemastore = function()
  return {
    json = {
      schemas = function()
        return catalog
      end,
    },
    yaml = {
      schemas = function()
        return { ["https://example.test/catalog"] = { "example.yaml" } }
      end,
    },
  }
end
local tests = {}

function tests.servers()
  -- schema-companion's adapter preserves root_dir/filetypes/settings; its extra
  -- callbacks handle schema selection. No plugin loading or external LSP here.
  package.preload["schema-companion"] = function()
    local function setup()
      return {}
    end
    return {
      setup_client = function(adapter, config)
        assert(adapter.sources[2].match == false, "LSP auto-matching must not rewrite global schema patterns")
        assert(type(adapter.sources[2].get_schemas) == "function", "manual schema listing remains available")
        return config
      end,
      adapters = {
        yamlls = {
          setup = function(config)
            return { sources = config.sources }
          end,
        },
      },
      sources = {
        matchers = { kubernetes = { setup = setup } },
        lsp = {
          setup = function()
            return { match = function() end, get_schemas = function() end }
          end,
        },
      },
    }
  end
  local opts = { servers = {} }
  for _, name in ipairs({ "json", "yaml", "rust" }) do
    for _, spec in ipairs(require("plugins." .. name)) do
      if spec[1] == "neovim/nvim-lspconfig" then
        if type(spec.opts) == "function" then
          spec.opts(nil, opts)
        else
          opts = vim.tbl_deep_extend("force", opts, spec.opts)
        end
      end
    end
  end
  for server, ft in pairs({ jsonls = "json", yamlls = "yaml", tombi = "toml" }) do
    local config = opts.servers[server]
    assert(vim.tbl_contains(config.filetypes, ft))
    assert(vim.tbl_contains(config.filetypes, ft .. ".chezmoitmpl"))
    assert(config.get_language_id(0, ft .. ".chezmoitmpl") == ft)
  end
  assert(opts.servers.jsonls.get_language_id(0, "jsonc.chezmoitmpl") == "jsonc")
  local project = scratch .. "/répô"
  vim.fn.mkdir(project .. "/.git", "p")
  vim.fn.mkdir(project .. "/config", "p")
  local buf = vim.api.nvim_create_buf(false, false)
  vim.api.nvim_buf_set_name(buf, project .. "/config/deleted.yml")
  local selected, called
  local function on_dir(dir)
    selected, called = dir, true
  end
  opts.servers.yamlls.root_dir(buf, on_dir)
  assert(called and selected == project, "native root callback must receive the project")
  vim.fn.writefile({ "name: example" }, project .. "/Chart.yaml")
  called = false
  opts.servers.yamlls.root_dir(buf, on_dir)
  assert(not called, "Helm files must not start standalone yamlls")
  vim.fn.delete(project .. "/Chart.yaml")
  opts.servers.yamlls.root_dir(buf, on_dir)
  assert(called, "removing the Helm marker restores standalone YAML")
end

function tests.format()
  local format = require("util.format")
  local buf = vim.api.nvim_create_buf(false, true)
  local calls = 0
  format.register({
    name = "test native formatter",
    sources = function()
      return { "native" }
    end,
    format = function(buffer)
      calls = calls + 1
      vim.api.nvim_buf_set_lines(buffer, 0, -1, false, { "formatted" })
    end,
  })
  for _, ft in ipairs({ "json", "jsonc", "yaml", "toml" }) do
    vim.bo[buf].filetype = ft .. ".chezmoitmpl"
    local lines = { "{{ if .enabled }}", 'value = "café"', "{{ end }}" }
    vim.api.nvim_buf_set_lines(buf, 0, -1, false, lines)
    local before = calls
    format.format({ buf = buf })
    assert(calls == before and vim.deep_equal(vim.api.nvim_buf_get_lines(buf, 0, -1, false), lines))
    vim.bo[buf].filetype = ft
    format.format({ buf = buf })
    assert(calls == before + 1, "normal configs must still format")
  end
end

assert(tests[arg[1]], "unknown test case")()
print("PASS " .. arg[1])
