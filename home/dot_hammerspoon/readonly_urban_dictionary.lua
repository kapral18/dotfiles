local M = { title = "Urban Dictionary", hint = "ud <word or phrase>" }
local API = "https://api.urbandictionary.com/v0/"
local PAGE = "https://www.urbandictionary.com/define.php?term="

local function encode(value)
  return (value:gsub("([^%w%-_%.~])", function(byte)
    return string.format("%%%02X", string.byte(byte))
  end))
end

local function request(endpoint, term, is_current, callback)
  hs.http.asyncGet(API .. endpoint .. "?term=" .. encode(term), nil, function(status, body)
    if not is_current() then
      return
    end
    local ok, data = pcall(hs.json.decode, body)
    callback(status == 200 and ok and type(data) == "table" and data or nil)
  end)
end

local function top_definition(data, term)
  local best
  for _, entry in ipairs(data and type(data.list) == "table" and data.list or {}) do
    if type(entry) == "table" and type(entry.word) == "string" and type(entry.definition) == "string" then
      if
        entry.word:lower() == term:lower()
        and (not best or (tonumber(entry.thumbs_up) or 0) > (tonumber(best.thumbs_up) or 0))
      then
        best = entry
      end
    end
  end
  return best
end

local function load_definitions(terms, publish, is_current)
  local choices = {}
  for _, term in ipairs(terms) do
    if type(term) == "string" then
      choices[#choices + 1] = { text = term, subText = "Loading definition…", url = PAGE .. encode(term) }
    end
  end
  if #choices == 0 then
    publish({ { text = "No matching terms", valid = false } })
    return
  end
  publish(choices)
  for index, choice in ipairs(choices) do
    local row = index
    request("define", choice.text, is_current, function(data)
      local entry = top_definition(data, choice.text)
      if entry then
        choices[row].subText = entry.definition:gsub("[%[%]]", ""):gsub("%s+", " "):gsub("^%s*(.-)%s*$", "%1")
        local id = tonumber(entry.defid)
        if id and id > 0 and id == math.floor(id) then
          choices[row].url = choices[row].url .. "&defid=" .. string.format("%.0f", id)
        end
      else
        choices[row].subText = data and "No definition returned — Enter to open website"
          or "Definition unavailable — Enter to open website"
      end
      publish(choices)
    end)
  end
end

function M.search(term, publish, is_current)
  request("autocomplete", term, is_current, function(terms)
    if not terms then
      publish({ { text = "Urban Dictionary unavailable — edit your query to try again", valid = false } })
      return
    end
    load_definitions(terms, publish, is_current)
  end)
end

return M
