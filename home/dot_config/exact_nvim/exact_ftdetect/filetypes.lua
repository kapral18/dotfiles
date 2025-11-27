-- Check if a file is inside a Helm chart (has Chart.yaml in parent hierarchy)
local function is_helm_chart_file(path)
  local dir = vim.fn.fnamemodify(path, ":h")
  -- Walk up the directory tree looking for Chart.yaml
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
    ["http"] = "http",
  },
  filename = {
    -- Explicit helm files
    ["helmfile.yaml"] = "helm",
    ["helmfile.yml"] = "helm",
    -- Docker compose files
    ["docker-compose.yaml"] = "yaml.docker-compose",
    ["docker-compose.yml"] = "yaml.docker-compose",
    ["compose.yaml"] = "yaml.docker-compose",
    ["compose.yml"] = "yaml.docker-compose",
  },
  pattern = {
    -- Docker compose files (with environment suffix like docker-compose.prod.yaml)
    ["docker%-compose%..*%.ya?ml"] = "yaml.docker-compose",
    ["compose%..*%.ya?ml"] = "yaml.docker-compose",

    -- All YAML files in Helm chart directories get helm filetype
    [".*%.ya?ml"] = function(path)
      if is_helm_chart_file(path) then
        return "helm"
      end
    end,

    -- Helm template partials (.tpl files)
    [".*%.tpl"] = function(path)
      if is_helm_chart_file(path) then
        return "helm"
      end
    end,

    -- NOTES.txt in templates is also helm
    [".*/templates/NOTES%.txt"] = "helm",
  },
})
