#!/usr/bin/env bash
# Load the mod on a new map and, when supplied, once on each save archive.
set -uo pipefail

here="$(cd "$(dirname "$0")" && pwd)"
py() { python3 -I "$here/$1" "${@:2}"; }

mod_path="${MOD_PATH:-}"
mods_lock="${MODS_LOCK:-}"
mods_cache="${MODS_CACHE:-}"
work_dir="${WORK_DIR:-}"
game="${FACTORIO_GAME_VERSION:-}"
ticks="${FACTORIO_TICKS:-600}"
saves="${FACTORIO_SAVES:-}"
settings="${FACTORIO_SETTINGS:-}"

fail() {
  echo "error: $*" >&2
  if [ -n "${GITHUB_STEP_SUMMARY:-}" ]; then
    {
      echo "### Factorio load failed"
      echo
      echo "$*"
    } >> "$GITHUB_STEP_SUMMARY"
  fi
  exit 1
}

[[ "$ticks" =~ ^[0-9]+$ ]] && [ "$ticks" -gt 0 ] || fail "ticks must be a positive integer"
[ -d "$mod_path" ] || fail "mod path does not exist"
[ -f "$mods_lock" ] || fail "resolved mod lock is missing"
[ -d "$mods_cache" ] || mkdir -p "$mods_cache" || fail "cannot create the mod cache"
[ -n "$work_dir" ] || fail "working directory is missing"

py mods.py fetch --lock "$mods_lock" --dir "$mods_cache" || fail "could not download the required mods"

game_dir="$work_dir/factorio-$game"
factorio_bin="$game_dir/factorio/bin/x64/factorio"
if [ ! -x "$factorio_bin" ]; then
  if [ "$(uname -s)-$(uname -m)" != "Linux-x86_64" ]; then
    fail "the headless build requires a Linux x64 runner"
  fi
  echo "Downloading Factorio $game headless"
  mkdir -p "$game_dir" || fail "cannot create the Factorio directory"
  if ! curl -fSL --retry 3 --retry-delay 2 \
    -o "$game_dir/factorio.tar.xz" \
    "https://factorio.com/get-download/$game/headless/linux64"; then
    fail "could not download Factorio $game"
  fi
  tar -xJf "$game_dir/factorio.tar.xz" -C "$game_dir" || fail "could not unpack Factorio $game"
  rm -f "$game_dir/factorio.tar.xz"
fi

built="$("$factorio_bin" --version < /dev/null | sed -n 's/^Version: \([0-9.]*\).*/\1/p' | head -1)"
[ "$built" = "$game" ] || fail "downloaded Factorio $built, expected $game"
echo "Factorio $game"

mods_dir="$work_dir/mods"
py mods.py assemble --lock "$mods_lock" --cache "$mods_cache" --mod-path "$mod_path" --out "$mods_dir" \
  || fail "could not assemble the mod directory"
if [ -n "$settings" ]; then
  py mod_settings.py write "$mods_dir/mod-settings.dat" --game "$game" --settings "$settings" \
    || fail "could not write startup settings"
fi

run_case() {
  local name="$1" run_dir="$2"; shift 2
  local output="$run_dir/$name.txt" log="$run_dir/factorio-current.log" code error_line
  mkdir -p "$run_dir/config" || fail "cannot create the Factorio run directory"
  printf '[path]\nread-data=__PATH__executable__/../../data\nwrite-data=%s\n[other]\nenable-new-mods=false\n' "$run_dir" > "$run_dir/config.ini"
  echo "Running $name"
  if timeout --signal=TERM 1500 "$factorio_bin" -c "$run_dir/config.ini" --mod-directory "$mods_dir" "$@" \
    < /dev/null > "$output" 2>&1; then
    echo "ok   $name"
    if [ -n "${GITHUB_STEP_SUMMARY:-}" ]; then
      printf '| %s | ok |\n' "$name" >> "$GITHUB_STEP_SUMMARY"
    fi
    return 0
  else
    code=$?
  fi
  error_line="$(awk '/ Error |Failed to load|Error:/ { print; exit }' "$log" "$output" 2>/dev/null | cut -c1-900)"
  [ -n "$error_line" ] || error_line="$(tail -n 20 "$output" 2>/dev/null | cut -c1-900)"
  echo "::error title=Factorio load failed::${name} exited with code $code"
  if [ -n "$error_line" ]; then
    printf '%s\n' "$error_line" >&2
  fi
  if [ -n "${GITHUB_STEP_SUMMARY:-}" ]; then
    {
      printf '| %s | FAILED, exit code %s |\n\n' "$name" "$code"
      echo 'First error from the Factorio log or command output:'
      echo
      echo '```text'
      printf '%s\n' "$error_line"
      echo '```'
    } >> "$GITHUB_STEP_SUMMARY"
  fi
  return 1
}

if [ -n "${GITHUB_STEP_SUMMARY:-}" ]; then
  {
    echo "### Factorio load, version $game"
    echo
    echo '| Run | Result |'
    echo '| --- | --- |'
  } >> "$GITHUB_STEP_SUMMARY"
fi

new_game_dir="$work_dir/new-game"
mkdir -p "$new_game_dir" || fail "cannot create the new-game directory"
run_case "new map create" "$new_game_dir" --create "$new_game_dir/map.zip" || exit $?
[ -s "$new_game_dir/map.zip" ] || fail "Factorio did not create a map archive"
run_case "new map ticks" "$new_game_dir" --benchmark "$new_game_dir/map.zip" \
  --benchmark-ticks "$ticks" --benchmark-runs 1 || exit $?

if [ -n "$saves" ]; then
  if [[ "$saves" = /* ]]; then
    saves_dir="$saves"
  else
    saves_dir="$GITHUB_WORKSPACE/$saves"
  fi
  [ -d "$saves_dir" ] || fail "saves directory does not exist: $saves"
  shopt -s nullglob
  save_files=("$saves_dir"/*.zip)
  if [ "${#save_files[@]}" -eq 0 ]; then
    echo "No save archives found in $saves"
  fi
  index=0
  for save in "${save_files[@]}"; do
    index=$((index + 1))
    save_name="$(basename "$save" .zip)"
    save_dir="$work_dir/save-$index"
    mkdir -p "$save_dir" || fail "cannot create the run directory for $save_name"
    run_case "save $save_name" "$save_dir" --benchmark "$save" \
      --benchmark-ticks "$ticks" --benchmark-runs 1 || exit $?
  done
fi

echo "Loaded $mod_path in Factorio $game"
