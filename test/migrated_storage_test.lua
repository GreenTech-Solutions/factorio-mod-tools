-- Unit test of lua/migrated_storage.lua on a mocked storage; run from the repository root:
--   ~/.local/share/factorio-lua/5.2/bin/lua test/migrated_storage_test.lua
package.path = "./lua/?.lua;" .. package.path
local logs = {}
rawset(_G, "log", function(message) logs[#logs + 1] = message end)
local migrated_storage = require("migrated_storage")

local function check(value, message)
  if not value then error(message, 2) end
end

-- nothing migrated
rawset(_G, "storage", {})
check(migrated_storage.take({"original"}) == nil and #logs == 0, "Took something without storage._migrated")

-- the first listed name that the game migrated wins, other removed mods stay
local old_state = {surfaces = {nauvis = true}, count = 3}
rawset(_G, "storage", {_migrated = {original = old_state, ["other-mod"] = {x = 1}}})
local old, name = migrated_storage.take({"missing", "original"})
check(old == old_state and name == "original", "Did not take the storage of the original")
check(storage._migrated.original == nil and storage._migrated["other-mod"].x == 1, "Storage of another mod was lost")
check(#logs == 1 and logs[1]:find("original", 1, true), "Expected one log line naming the original")
check(migrated_storage.take({"original"}) == nil, "Took the same storage twice")

-- the last one taken removes storage._migrated
rawset(_G, "storage", {_migrated = {original = {count = 1}}})
migrated_storage.take({"original"})
check(storage._migrated == nil, "An empty storage._migrated was left behind")

-- adopt copies only the keys storage does not have
rawset(_G, "storage", {count = 10})
local copied = migrated_storage.adopt({count = 3, surfaces = {}, _migrated = {x = {}}})
check(copied == 1 and storage.count == 10 and storage.surfaces and storage._migrated == nil,
  "adopt has to copy only missing keys and never _migrated")

print("migrated_storage: ok")
