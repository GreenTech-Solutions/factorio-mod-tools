#!/usr/bin/env python3
"""Check that every sound and image path a mod's Lua names exists.

A wrong path passes luac, luacheck, emmylua_check and every headless test: a headless game never loads sounds or
images. A game with graphics refuses to start with the mod.

  lua/check-assets.py [mod directory]             default: the current directory
  lua/check-assets.py --write-game-list [data]    rebuild lua/game-assets.txt.gz from a game's data folder

Checks every string literal "__<mod>__/<path>.<ogg|wav|png|jpg>" in the mod's .lua files, outside comments and outside
the top-level tests/, test/ and spec/ folders (unit tests name made-up paths). Paths put together with .. and
string.format templates are not checked:
  - __<this mod>__/…: against the mod folder, where "this mod" is "name" in info.json;
  - __base__, __core__, __space-age__, __quality__, __elevated-rails__, __recycler__: against the game data, which is
    $FACTORIO_DATA, else a game installed in a usual place, else lua/game-assets.txt.gz (the list of these files in the
    version it names, which is what CI uses: wube/factorio-data has no graphics or sounds);
  - other mods: skipped with a note.
Paths are compared with their case: the game reads them case-sensitively on Linux.

Prints file:line: error: message and exits 1 on any missing path.
"""
import gzip
import json
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

GAME_MODS = ("base", "core", "space-age", "quality", "elevated-rails", "recycler")
# unit tests outside the game name made-up paths
SKIP_DIRS = (".git", "node_modules", "tests", "test", "spec")
EXTENSIONS = (".ogg", ".wav", ".png", ".jpg")
GAME_LIST = Path(__file__).resolve().parent / "game-assets.txt.gz"
GAME_DIRS = (
    "~/Library/Application Support/Steam/steamapps/common/Factorio/factorio.app/Contents/data",
    "/Applications/factorio.app/Contents/data",
    "~/.steam/steam/steamapps/common/Factorio/data",
    "~/.local/share/Steam/steamapps/common/Factorio/data",
)
LONG_BRACKET = re.compile(r"\[(=*)\[")
PATH = re.compile(r"^__(?P<mod>[^_/][^/]*?)__/(?P<path>.+)$")


def strings(text: str):
    """Yield (line, value) of every short string literal in Lua source, skipping comments and long strings."""
    i, line, n = 0, 1, len(text)
    while i < n:
        c = text[i]
        if c == "\n":
            line += 1
            i += 1
        elif text.startswith("--", i) or c == "[" and LONG_BRACKET.match(text, i):
            start = i + 2 if c == "-" else i
            bracket = LONG_BRACKET.match(text, start)
            if bracket:
                close = "]" + bracket.group(1) + "]"
                end = text.find(close, start + len(bracket.group(0)))
                end = n if end < 0 else end + len(close)
            else:
                end = text.find("\n", i)
                end = n if end < 0 else end
            line += text.count("\n", i, end)
            i = end
        elif c in "\"'":
            j, value, start_line = i + 1, [], line
            while j < n and text[j] != c and text[j] != "\n":
                if text[j] == "\\" and j + 1 < n:
                    if text[j + 1] == "\n":
                        line += 1
                    value.append(text[j:j + 2])
                    j += 2
                else:
                    value.append(text[j])
                    j += 1
            yield start_line, "".join(value)
            i = j + 1
        else:
            i += 1


def lua_files(mod: Path):
    for path in sorted(mod.rglob("*.lua")):
        parts = path.relative_to(mod).parts
        if parts and parts[0] in SKIP_DIRS:
            continue
        yield path


def assets_under(directory: Path) -> set:
    """Paths relative to directory of the sound and image files under it."""
    found = set()
    for current, dirs, files in os.walk(directory):
        dirs[:] = [d for d in dirs if d not in (".git", "node_modules")]
        relative = Path(current).relative_to(directory).as_posix()
        prefix = "" if relative == "." else relative + "/"
        found.update(prefix + name for name in files if name.lower().endswith(EXTENSIONS))
    return found


def game_files(data: Path) -> set:
    """Paths "<mod>/<path>" of the sound and image files of the game mods under a data folder."""
    return {f"{mod}/{path}" for mod in GAME_MODS for path in assets_under(data / mod)}


def game_version(data: Path) -> str:
    try:
        return json.loads((data / "base" / "info.json").read_text(encoding="utf-8"))["version"]
    except (OSError, ValueError, KeyError):
        return "unknown version"


def game_assets():
    """(set of "<mod>/<path>", description of the source)."""
    candidates = [os.environ["FACTORIO_DATA"]] if os.environ.get("FACTORIO_DATA") else list(GAME_DIRS)
    for candidate in candidates:
        data = Path(candidate).expanduser()
        if (data / "base" / "graphics").is_dir():
            return game_files(data), f"Factorio {game_version(data)} at {data}"
    if os.environ.get("FACTORIO_DATA"):
        sys.exit(f"error: FACTORIO_DATA={os.environ['FACTORIO_DATA']} has no base/graphics")
    with gzip.open(GAME_LIST, "rt", encoding="utf-8") as file:
        lines = file.read().splitlines()
    return {line for line in lines if not line.startswith("#")}, f"{lines[0].lstrip('# ')} ({GAME_LIST.name})"


def write_game_list(data: Path) -> int:
    if not (data / "base" / "graphics").is_dir():
        print(f"error: {data} has no base/graphics; give the data folder of a game with graphics", file=sys.stderr)
        return 1
    paths = sorted(game_files(data))
    # mtime=0 keeps the file the same when the list is
    with open(GAME_LIST, "wb") as raw, gzip.GzipFile(fileobj=raw, mode="wb", compresslevel=9, mtime=0) as file:
        file.write("\n".join([f"# Factorio {game_version(data)}", *paths, ""]).encode("utf-8"))
    print(f"{GAME_LIST}: {len(paths)} files of Factorio {game_version(data)}")
    return 0


def check(mod: Path):
    """(problems, number of checked paths, Counter of skipped mods, source of the game files)."""
    try:
        name = json.loads((mod / "info.json").read_text(encoding="utf-8"), strict=False).get("name", "")
    except (OSError, ValueError):
        name = ""
    references = []
    for path in lua_files(mod):
        for line, value in strings(path.read_text(encoding="utf-8", errors="replace")):
            match = PATH.match(value)
            # "%" is a string.format template, "\\" an escape this scan does not decode
            if match and value.lower().endswith(EXTENSIONS) and not set(value) & {"%", "\\"}:
                references.append((path.relative_to(mod).as_posix(), line, match.group("mod"), match.group("path")))

    own = assets_under(mod)
    game, source = (game_assets() if any(ref[2] in GAME_MODS for ref in references) else (set(), None))
    by_name = defaultdict(list)
    for path in game:
        by_name[path.rsplit("/", 1)[-1]].append(path)

    problems, checked, skipped = [], 0, Counter()
    for file, line, owner, path in references:
        if owner == name and name:
            checked += 1
            if path not in own:
                problems.append(f"{file}:{line}: error: __{owner}__/{path} is not in the mod folder")
        elif owner in GAME_MODS:
            checked += 1
            if f"{owner}/{path}" not in game:
                near = sorted(f"__{p.replace('/', '__/', 1)}" for p in by_name.get(path.rsplit("/", 1)[-1], []))
                hint = f"; did you mean {' or '.join(near[:3])}" if near else ""
                problems.append(f"{file}:{line}: error: __{owner}__/{path} is not in the game files{hint}")
        else:
            skipped[owner] += 1
    return problems, checked, skipped, source


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "--write-game-list":
        return write_game_list(Path(sys.argv[2] if len(sys.argv) > 2 else GAME_DIRS[0]).expanduser())
    mod = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    problems, checked, skipped, source = check(mod)
    for problem in problems:
        print(problem)
    if skipped:
        print("assets: skipped paths into other mods: "
              + ", ".join(f"__{owner}__ ({count})" for owner, count in sorted(skipped.items())))
    print(f"assets: {checked} paths checked{f' against {source}' if source else ''}, {len(problems)} missing")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
