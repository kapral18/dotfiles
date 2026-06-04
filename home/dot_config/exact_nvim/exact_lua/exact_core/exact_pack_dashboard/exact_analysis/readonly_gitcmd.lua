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
local commit_records_cache = {}

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

-- Per-commit `{ hash, message }` records for the range, newest first, where
-- `hash` is the short hash and `message` is the full commit message (subject +
-- body). Preserves commit boundaries so callers can attribute a breaking marker
-- to the specific commit that carries it (in subject OR body) and key it by
-- hash. Uses ASCII record/unit separators (RS \30, US \31) as delimiters: git
-- never emits them in messages.
local function commit_records_between(path, rev_before, rev_after)
  local key = range_key(path, rev_before, rev_after)
  if not key then
    return nil
  end
  if commit_records_cache[key] ~= nil then
    return commit_records_cache[key] or nil
  end

  local result = vim
    .system({ "git", "-C", path, "log", "--format=%h%x1f%s%n%b%x1e", rev_before .. ".." .. rev_after }, { text = true })
    :wait()
  if result.code ~= 0 or type(result.stdout) ~= "string" then
    commit_records_cache[key] = false
    return nil
  end

  local records = {}
  for _, record in ipairs(vim.split(result.stdout, "\30", { trimempty = true })) do
    local hash, message = record:match("^%s*(%x+)\31(.*)$")
    if hash and hash ~= "" then
      records[#records + 1] = { hash = hash, message = vim.trim(message or "") }
    end
  end

  commit_records_cache[key] = #records > 0 and records or false
  return commit_records_cache[key] or nil
end

M.tags_on_revision = tags_on_revision
M.all_tags = all_tags
M.tag_on_revision = tag_on_revision
M.commit_messages_between = commit_messages_between
M.commit_records_between = commit_records_between

return M
