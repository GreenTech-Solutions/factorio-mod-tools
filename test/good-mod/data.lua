local recipe = data.raw.recipe["iron-gear-wheel"]
if recipe then
  recipe.energy_required = 0.5
  log("good-mod: iron-gear-wheel crafts in " .. recipe.energy_required .. " s")
end

-- sound and image paths the asset check finds: in the game, in this mod, in another mod (skipped)
-- "__base__/sound/alarm-1.ogg" in a comment is not checked
local sprites = {
  alarm = "__base__/sound/programmable-speaker/alarm-1.ogg",
  icon = "__good-mod__/graphics/icon.png",
  other = "__some-other-mod__/graphics/icon.png",
}
log("good-mod: " .. sprites.alarm .. ", " .. sprites.icon .. ", " .. sprites.other)
