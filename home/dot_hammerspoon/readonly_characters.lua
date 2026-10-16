local fold = require("search_text")

local symbols = {
  { "→", "right arrow", "->" },
  { "←", "left arrow", "<-" },
  { "↑", "up arrow", "" },
  { "↓", "down arrow", "" },
  { "↔", "left right arrow", "<-> bidirectional" },
  { "⇒", "right double arrow", "=> implies" },
  { "⇐", "left double arrow", "<=" },
  { "⇔", "left right double arrow", "<=> equivalent" },
  { "↳", "down right arrow", "return branch" },
  { "↗", "up right arrow", "northeast" },
  { "↘", "down right arrow", "southeast" },
  { "⏎", "return", "enter" },
  { "⌘", "command", "cmd mac apple" },
  { "⌥", "option", "alt mac" },
  { "⌃", "control", "ctrl mac" },
  { "⇧", "shift", "mac" },
  { "⇥", "tab", "mac" },
  { "⎋", "escape", "esc mac" },
  { "⌫", "delete", "backspace mac" },
  { "✓", "check mark", "yes done tick" },
  { "✗", "cross mark", "no wrong" },
  { "•", "bullet", "dot list" },
  { "·", "middle dot", "separator" },
  { "…", "ellipsis", "three dots" },
  { "—", "em dash", "long dash" },
  { "–", "en dash", "short dash" },
  { "“", "left double quotation mark", "opening quote smart" },
  { "”", "right double quotation mark", "closing quote smart" },
  { "‘", "left single quotation mark", "opening quote smart" },
  { "’", "right single quotation mark", "apostrophe closing quote smart" },
  { "«", "left guillemet", "opening angle quote" },
  { "»", "right guillemet", "closing angle quote" },
  { "≠", "not equal", "!=" },
  { "≈", "approximately equal", "almost ~= estimate" },
  { "≤", "less than or equal", "<=" },
  { "≥", "greater than or equal", ">=" },
  { "±", "plus minus", "+/-" },
  { "×", "multiplication", "multiply times" },
  { "÷", "division", "divide" },
  { "∞", "infinity", "unlimited" },
  { "√", "square root", "sqrt radical" },
  { "∑", "summation", "sum sigma" },
  { "∈", "element of", "set member" },
  { "∅", "empty set", "null" },
  { "∧", "logical and", "conjunction" },
  { "∨", "logical or", "disjunction" },
  { "¬", "logical not", "negation" },
  { "°", "degree", "temperature angle" },
  { "µ", "micro", "mu" },
  { "π", "pi", "circle" },
  { "²", "superscript two", "squared" },
  { "³", "superscript three", "cubed" },
  { "½", "one half", "fraction 1/2" },
  { "¼", "one quarter", "fraction 1/4" },
  { "¾", "three quarters", "fraction 3/4" },
  { "€", "euro", "currency" },
  { "£", "pound sterling", "currency gbp" },
  { "¥", "yen yuan", "currency jpy cny" },
  { "₴", "hryvnia", "currency uah ukraine" },
  { "©", "copyright", "" },
  { "®", "registered trademark", "" },
  { "™", "trademark", "tm" },
  { "§", "section", "legal paragraph" },
  { "¶", "pilcrow", "paragraph" },
}

local function normalize(text)
  return fold(text):gsub("_", " ")
end

local function provider(title, hint, data)
  local keywords = {}
  for index, item in ipairs(data) do
    keywords[index] = item[2] .. " " .. item[3]
  end
  keywords = fold(keywords)
  local entries = {}
  for index, item in ipairs(data) do
    entries[#entries + 1] = {
      text = item[1] .. "  " .. item[2],
      subText = "Enter to copy · " .. item[3],
      copy = item[1],
      keywords = keywords[index]:gsub("_", " "),
    }
  end
  return {
    title = title,
    hint = hint,
    immediate = true,
    search = function(term, publish)
      local words = {}
      for literal in term:gmatch("%S+") do
        for word in normalize(literal):gmatch("%S+") do
          words[#words + 1] = { search = word, literal = literal }
        end
      end
      local choices = {}
      for _, entry in ipairs(entries) do
        local matches = true
        for _, word in ipairs(words) do
          if
            not entry.keywords:find(word.search, 1, true)
            and entry.copy ~= word.literal
            and entry.copy ~= word.search
          then
            matches = false
            break
          end
        end
        if matches then
          choices[#choices + 1] = entry
        end
      end
      if #choices == 0 then
        choices[1] = { text = "No matching characters", valid = false }
      end
      publish(choices)
    end,
  }
end

return {
  emoji = provider("Emoji", "emoji <name or keyword>", require("emoji")),
  symbols = provider("Symbols", "sym <name or keyword>", symbols),
}
