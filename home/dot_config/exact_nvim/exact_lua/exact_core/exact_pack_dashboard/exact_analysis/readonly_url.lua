local M = {}

local function parse_source_coordinates(src)
  if type(src) ~= "string" or src == "" then
    return nil
  end

  local normalized = vim.trim(src):gsub("/+$", "")
  local host, owner, repo = normalized:match("^https?://([^/]+)/([^/]+)/([^/]+)%.git$")
  if not host then
    host, owner, repo = normalized:match("^https?://([^/]+)/([^/]+)/([^/]+)$")
  end
  if not host then
    host, owner, repo = normalized:match("^git@([^:]+):([^/]+)/([^/]+)%.git$")
  end
  if not host then
    host, owner, repo = normalized:match("^git@([^:]+):([^/]+)/([^/]+)$")
  end
  if not host then
    host, owner, repo = normalized:match("^ssh://git@([^/]+)/([^/]+)/([^/]+)%.git$")
  end
  if not host then
    host, owner, repo = normalized:match("^ssh://git@([^/]+)/([^/]+)/([^/]+)$")
  end
  if not host or not owner or not repo then
    return nil
  end

  repo = repo:gsub("%.git$", "")
  return host, owner, repo
end

local function source_to_compare_url(src, rev_before, rev_after)
  if type(src) ~= "string" or src == "" or type(rev_before) ~= "string" or type(rev_after) ~= "string" then
    return nil
  end

  local host, owner, repo = parse_source_coordinates(src)
  if not host or not owner or not repo then
    return nil
  end

  if host == "github.com" or host == "codeberg.org" then
    return ("https://%s/%s/%s/compare/%s...%s"):format(host, owner, repo, rev_before, rev_after)
  end
  return nil
end

local function source_to_repo_url(src)
  if type(src) ~= "string" or src == "" then
    return nil
  end

  local host, owner, repo = parse_source_coordinates(src)
  if not host or not owner or not repo then
    return nil
  end
  return ("https://%s/%s/%s"):format(host, owner, repo)
end

local function repo_to_compare_url(repo_url, from_ref, to_ref)
  if type(repo_url) ~= "string" or repo_url == "" then
    return nil
  end
  if type(from_ref) ~= "string" or from_ref == "" or type(to_ref) ~= "string" or to_ref == "" then
    return nil
  end

  local host, owner, repo = repo_url:match("^https://([^/]+)/([^/]+)/([^/]+)$")
  if not host or not owner or not repo then
    return nil
  end
  if host == "github.com" or host == "codeberg.org" then
    return ("%s/compare/%s...%s"):format(repo_url, from_ref, to_ref)
  end
  return nil
end

M.parse_source_coordinates = parse_source_coordinates
M.source_to_compare_url = source_to_compare_url
M.source_to_repo_url = source_to_repo_url
M.repo_to_compare_url = repo_to_compare_url

return M
