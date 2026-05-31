local semver = require("core.pack.semver")

local M = {}

local semver_major = semver.semver_major

-- Per-process caches keyed by `path[@rev]`. Tags rarely change within a single
-- nvim session, and these queries shell out to git, so caching keeps the
-- dashboard render path cheap on repeated opens.
local revision_tag_cache = {}
local revision_tags_cache = {}
local repo_tags_cache = {}
local commit_messages_cache = {}
local commit_subjects_cache = {}

local function git_tags(path, args, cache, key)
  if type(path) ~= "string" or path == "" then
    return {}
  end
  if cache[key] ~= nil then
    return cache[key]
  end

  local command = { "git", "-C", path, "tag" }
  vim.list_extend(command, args)
  local result = vim.system(command, { text = true }):wait()
  if result.code ~= 0 or type(result.stdout) ~= "string" then
    cache[key] = {}
    return cache[key]
  end

  cache[key] = vim.split(result.stdout, "\n", { trimempty = true })
  return cache[key]
end

local function tags_on_revision(path, rev)
  if type(rev) ~= "string" or rev == "" then
    return {}
  end
  local key = path .. "@" .. rev
  return git_tags(path, { "--sort=-v:refname", "--points-at", rev }, revision_tags_cache, key)
end

local function all_tags(path)
  return git_tags(path, { "--list", "--sort=-v:refname" }, repo_tags_cache, path)
end

local function tag_on_revision(path, rev)
  if type(path) ~= "string" or path == "" or type(rev) ~= "string" or rev == "" then
    return nil
  end
  local key = path .. "@" .. rev
  if revision_tag_cache[key] ~= nil then
    return revision_tag_cache[key]
  end

  local result = vim.system({ "git", "-C", path, "tag", "--points-at", rev }, { text = true }):wait()
  if result.code ~= 0 or type(result.stdout) ~= "string" then
    revision_tag_cache[key] = false
    return nil
  end

  local tags = {}
  for _, line in ipairs(vim.split(result.stdout, "\n", { trimempty = true })) do
    if line ~= "" then
      tags[#tags + 1] = line
    end
  end

  table.sort(tags, function(a, b)
    local ma, mb = semver_major(a) or -1, semver_major(b) or -1
    if ma ~= mb then
      return ma > mb
    end
    return a > b
  end)

  revision_tag_cache[key] = tags[1] or false
  return revision_tag_cache[key] or nil
end

-- Both range queries below share the same arg contract: non-empty path and
-- both endpoints. Returns the cache key when valid, nil otherwise.
local function range_key(path, rev_before, rev_after)
  if
    type(path) ~= "string"
    or path == ""
    or type(rev_before) ~= "string"
    or rev_before == ""
    or type(rev_after) ~= "string"
    or rev_after == ""
  then
    return nil
  end
  return path .. "@" .. rev_before .. ".." .. rev_after
end

local function commit_messages_between(path, rev_before, rev_after)
  local key = range_key(path, rev_before, rev_after)
  if not key then
    return nil
  end
  if commit_messages_cache[key] ~= nil then
    return commit_messages_cache[key] or nil
  end

  local result = vim
    .system({ "git", "-C", path, "log", "--format=%s%n%b", rev_before .. ".." .. rev_after }, { text = true })
    :wait()
  if result.code ~= 0 or type(result.stdout) ~= "string" then
    commit_messages_cache[key] = false
    return nil
  end

  local normalized = vim.trim(result.stdout)
  commit_messages_cache[key] = normalized ~= "" and normalized or false
  return commit_messages_cache[key] or nil
end

local function commit_subjects_between(path, rev_before, rev_after)
  local key = range_key(path, rev_before, rev_after)
  if not key then
    return nil
  end
  if commit_subjects_cache[key] ~= nil then
    return commit_subjects_cache[key] or nil
  end

  local result = vim
    .system({ "git", "-C", path, "log", "--format=%s", rev_before .. ".." .. rev_after }, { text = true })
    :wait()
  if result.code ~= 0 or type(result.stdout) ~= "string" then
    commit_subjects_cache[key] = false
    return nil
  end

  local subjects = {}
  for _, line in ipairs(vim.split(result.stdout, "\n", { trimempty = true })) do
    local trimmed = vim.trim(line)
    if trimmed ~= "" then
      subjects[#subjects + 1] = trimmed
    end
  end

  commit_subjects_cache[key] = #subjects > 0 and subjects or false
  return commit_subjects_cache[key] or nil
end

M.tags_on_revision = tags_on_revision
M.all_tags = all_tags
M.tag_on_revision = tag_on_revision
M.commit_messages_between = commit_messages_between
M.commit_subjects_between = commit_subjects_between

return M
