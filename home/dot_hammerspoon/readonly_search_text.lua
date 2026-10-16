return function(value)
  local batch = type(value) == "table"
  local texts = batch and value or { value }
  local result, unicode, positions = {}, {}, {}
  for index, text in ipairs(texts) do
    if text:find("[\128-\255]") then
      unicode[#unicode + 1] = text
      positions[#positions + 1] = index
    else
      result[index] = text:lower()
    end
  end
  if #unicode > 0 then
    local ok, encoded = hs.osascript.javascript([[ObjC.import("Foundation");
      JSON.stringify(]] .. hs.json.encode(unicode) .. [[.map(function(text) {
        return $.NSString.alloc.initWithUTF8String(text).stringByFoldingWithOptionsLocale(
          $.NSCaseInsensitiveSearch | $.NSDiacriticInsensitiveSearch, $.NSLocale.currentLocale).js;
      }))]])
    assert(ok, "Could not normalize search text")
    for index, text in ipairs(hs.json.decode(encoded)) do
      result[positions[index]] = text
    end
  end
  return batch and result or result[1]
end
