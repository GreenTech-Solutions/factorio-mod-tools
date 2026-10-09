-- Base luacheck config for a Factorio mod, used by lua/check.sh. The mod's own .luacheckrc, if there is one, runs
-- right after this in the same environment, so it adds to these tables instead of replacing them:
--   read_globals[#read_globals + 1] = "PlanetsLib"
--   ignore[#ignore + 1] = "542"
--   files["weather/paracelsin.lua"] = { ignore = { "211" } }
std = "lua52"
max_line_length = false
exclude_files = { "node_modules/**", ".git/**" }

-- mods define their helpers as globals at the top level of a file
allow_defined_top = true

read_globals = {
  -- Factorio's globals across stages (https://lua-api.factorio.com/latest/auxiliary/libraries.html)
  "mods", "settings", "feature_flags", "defines", "util", "serpent", "log", "localised_print", "table_size",
  "game", "script", "remote", "commands", "rendering", "rcon", "helpers", "prototypes",
  table = { fields = { "deepcopy", "compare" } },
  -- units from __core__/lualib/util.lua
  "grams", "kg", "tons", "second", "minute", "hour", "meter",
}
-- data-stage code writes into data.raw
globals = { "data", "storage" }

ignore = {
  "131", -- unused global: luacheck checks file by file and does not see a helper used from another file
}
files = files or {}

local own, err = loadfile(".luacheckrc", "t", _ENV)
if own then
  own()
elseif not err:find("cannot open", 1, true) then
  error(err, 0)
end
