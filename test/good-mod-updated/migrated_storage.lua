-- Copied from GreenTech-Solutions/factorio-mod-tools (lua/migrated_storage.lua); the check fails if the copy differs.
--
-- A mod that replaces another one names it in "migrates_from" of info.json (Factorio 2.1.18+). When a save that had
-- the old mod is loaded without it, the game moves the old mod's storage to storage._migrated[old name], and its GUI
-- elements, render objects and script inventories to this mod. The storage stays there until this mod takes it, so
-- on_init and on_configuration_changed take it first, before they build their own state:
--
--   local migrated_storage = require("migrated_storage")
--   script.on_init(function()
--     local old = migrated_storage.take({"original-mod"})
--     if old then
--       migrated_storage.adopt(old)   -- or drop it, when its references are no longer valid
--     end
--     -- ...the usual setup, which keeps what adopt() brought in
--   end)
local migrated_storage = {}

--- Takes the storage of the first of `names` that the game migrated and removes it from storage._migrated.
--- Storage of other removed mods stays there. Returns the old storage table and its mod name, or nil.
---@param names string[]
---@return table?, string?
function migrated_storage.take(names)
  local pending = storage._migrated
  if type(pending) ~= "table" then
    return nil
  end
  for _, name in ipairs(names) do
    local old = pending[name]
    if old ~= nil then
      pending[name] = nil
      if next(pending) == nil then
        storage._migrated = nil
      end
      log("Took the storage of the removed mod " .. name)
      return old, name
    end
  end
  return nil
end

--- Copies every key of `old` that storage does not have yet into storage; keys storage already has stay as they are.
--- Returns the number of keys copied.
---@param old table
---@return integer
function migrated_storage.adopt(old)
  local copied = 0
  for key, value in pairs(old) do
    if key ~= "_migrated" and storage[key] == nil then
      storage[key] = value
      copied = copied + 1
    end
  end
  return copied
end

return migrated_storage
