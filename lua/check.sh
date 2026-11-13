#!/usr/bin/env bash
# Checks a Factorio mod; exits non-zero if any check fails. Needs lua/setup.sh once.
#   1. syntax of every .lua under Lua 5.2 (luac -p): catches 5.3+ syntax (//, &, |, ~, <<, >>) the game rejects
#   2. luacheck with lua/luacheckrc.lua, then the mod's .luacheckrc on top of it
#   3. emmylua_check with lua/emmyrc.json merged with the mod's .emmyrc.json, against the Factorio API library:
#      catches fields and functions the game does not have, like defines.default_icon_size after 2.1
#   4. changelog.txt against the format the game parses (lua/check-changelog.py)
#   5. info.json: a fork takes over the saves of the mod it replaces (migrates_from, lua/check-info.py)
#   lua/check.sh [mod directory]    default: the current directory
set -uo pipefail

here="$(cd "$(dirname "$0")" && pwd)"
mod="$(cd "${1:-.}" && pwd)" || exit 1
# shellcheck source=lua/versions.sh
source "$here/versions.sh"
root="${FACTORIO_LUA_HOME:-$HOME/.local/share/factorio-lua}"
bin="$root/5.2/bin"
emmylua="$root/emmylua/$emmylua_version/emmylua_check"
library="$root/fmtk/$factorio_api_version/factorio/library"
if [ ! -x "$bin/luac" ] || [ ! -x "$bin/luacheck" ] || [ ! -x "$emmylua" ] || [ ! -d "$library" ]; then
  echo "error: no check toolchain in $root; run $here/setup.sh" >&2
  exit 1
fi

cd "$mod" || exit 1
status=0

files=0
failed=0
while IFS= read -r -d '' file; do
  files=$((files + 1))
  if ! "$bin/luac" -p -- "$file"; then failed=$((failed + 1)); fi
done < <(find . -name '*.lua' -not -path './node_modules/*' -not -path './.git/*' -print0)
rm -f luac.out
echo "syntax (Lua 5.2): $files files, $failed failed"
[ "$failed" -eq 0 ] || status=1

"$bin/luacheck" --no-color --formatter plain --config "$here/luacheckrc.lua" . || status=1
echo "luacheck: done"

config=$(mktemp)
trap 'rm -f "$config" "$config.out"' EXIT
python3 - "$here/emmyrc.json" .emmyrc.json "$library" "$config" <<'PY'
import json, os, sys

def merge(base, own):
    """The mod's settings on top of the base: tables merge, lists add up, other values replace."""
    if isinstance(base, dict) and isinstance(own, dict):
        return {key: merge(base[key], own[key]) if key in base and key in own else own.get(key, base.get(key))
                for key in {**base, **own}}
    if isinstance(base, list) and isinstance(own, list):
        return base + [value for value in own if value not in base]
    return own

base_path, own_path, library, out = sys.argv[1:]
config = json.load(open(base_path))
if os.path.exists(own_path):
    config = merge(config, json.load(open(own_path)))
config.setdefault("workspace", {})["library"] = [library]
json.dump(config, open(out, "w"))
PY
"$emmylua" . -c "$config" --warnings-as-errors > "$config.out" 2>&1 || status=1
grep -v '^Check finished$' "$config.out"
echo "emmylua_check (Factorio $factorio_api_version API): done"

if [ -f changelog.txt ]; then
  python3 "$here/check-changelog.py" changelog.txt || status=1
else
  echo "changelog: no changelog.txt"
fi

python3 "$here/check-info.py" . || status=1

exit "$status"
