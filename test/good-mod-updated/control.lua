local migrated_storage = require("migrated_storage")

local function take_original()
  local old = migrated_storage.take({"good-mod"})
  if old then
    migrated_storage.adopt(old)
  end
end

script.on_init(function()
  take_original()
  storage.count = storage.count or 0
end)

script.on_configuration_changed(take_original)
