local recipe = data.raw.recipe["iron-gear-wheel"]
if recipe then
  recipe.energy_required = 0.5
  log("good-mod: iron-gear-wheel crafts in " .. recipe.energy_required .. " s")
end
