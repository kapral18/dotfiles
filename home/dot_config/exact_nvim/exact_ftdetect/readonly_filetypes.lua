local function is_helm_chart_file(path)
  local dir = vim.fn.fnamemodify(path, ":h")
  while dir ~= "/" and dir ~= "" do
    if vim.fn.filereadable(dir .. "/Chart.yaml") == 1 then
      return true
    end
    local parent = vim.fn.fnamemodify(dir, ":h")
    if parent == dir then
      break
    end
    dir = parent
  end
  return false
end

vim.filetype.add({
  extension = {
    log = "log",
    conf = "conf",
    env = "dotenv",
    mdx = "mdx",
    jsonl = "jsonl",
    ["http"] = "http",
  },
  filename = {
    [".env"] = "dotenv",
    ["env"] = "dotenv",
    ["tsconfig.json"] = "jsonc",
    [".*/kitty/.+%.conf"] = "kitty",
    ["helmfile.yaml"] = "helm",
    ["helmfile.yml"] = "helm",
    ["docker-compose.yaml"] = "yaml.docker-compose",
    ["docker-compose.yml"] = "yaml.docker-compose",
    ["compose.yaml"] = "yaml.docker-compose",
    ["compose.yml"] = "yaml.docker-compose",
  },
  pattern = {
    [".*_log$"] = "log",
    ["%.env%.[%w_.-]+"] = "dotenv",
    [".*%.yaml%.tmpl$"] = "gotexttmpl",
    [".*%.toml%.tmpl$"] = "gotexttmpl",
    [".*%.json%.tmpl$"] = "gotexttmpl",
    [".*%.jsonc%.tmpl$"] = "gotexttmpl",
    ["Dockerfile.*"] = "dockerfile",
    [".gitconfig.*"] = "gitconfig",
    ["docker%-compose%..*%.ya?ml"] = "yaml.docker-compose",
    ["compose%..*%.ya?ml"] = "yaml.docker-compose",
    [".*%.ya?ml"] = function(path)
      if is_helm_chart_file(path) then
        return "helm"
      end
    end,
    [".*%.tpl"] = function(path)
      if is_helm_chart_file(path) then
        return "helm"
      end
    end,
    [".*/templates/NOTES%.txt"] = "helm",
  },
})
