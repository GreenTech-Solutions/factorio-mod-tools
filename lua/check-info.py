#!/usr/bin/env python3
"""Check that a mod which replaces another one takes over its saves.

A fork named "<original>-updated" (also "-Updated", "-fork", "-legacy") replaces <original>. Since Factorio 2.1.18
"migrates_from" in info.json hands it the original's storage, GUI elements, render objects and script inventories when a
save that had the original is loaded with the fork; without it a player who switches loses the original's state.

  lua/check-info.py [mod directory]    default: the current directory

Rules:
  1. a fork lists its original in "migrates_from" and declares it incompatible ("! <original>"), so the two never run
     together and the game hands the state over only when the original is gone;
  2. a mod with "migrates_from" and a control.lua takes storage._migrated (through migrated_storage.lua or by itself),
     otherwise the old storage stays in the save, unused;
  3. migrated_storage.lua, where the mod has it, is the same as lua/migrated_storage.lua of these tools.

Prints file: error: message and exits 1 on any problem.
"""
import json
import re
import sys
from pathlib import Path

FORK_SUFFIX = re.compile(r"^(?P<original>.+?)[-_](updated|fork|legacy)$", re.IGNORECASE)
HELPER = Path(__file__).resolve().parent / "migrated_storage.lua"


def lua_files(mod: Path):
    for path in sorted(mod.rglob("*.lua")):
        parts = path.relative_to(mod).parts
        if parts and parts[0] in (".git", "node_modules"):
            continue
        yield path


def incompatible(dependencies) -> set:
    names = set()
    for dependency in dependencies or []:
        text = dependency.strip()
        if text.startswith("!"):
            names.add(re.split(r"\s|[<>=]", text[1:].strip(), maxsplit=1)[0])
    return names


def check(mod: Path) -> list:
    problems = []
    info_path = mod / "info.json"
    if not info_path.is_file():
        return ["info.json: error: no info.json"]
    info = json.loads(info_path.read_text(encoding="utf-8"), strict=False)
    name = info.get("name", "")
    migrates_from = info.get("migrates_from") or []
    if not isinstance(migrates_from, list) or not all(isinstance(item, str) for item in migrates_from):
        problems.append("info.json: error: migrates_from has to be a list of mod names")
        migrates_from = []

    fork = FORK_SUFFIX.match(name)
    if fork:
        original = fork.group("original")
        if original not in migrates_from:
            problems.append(f'info.json: error: {name} replaces {original}, add "migrates_from": ["{original}"] '
                            "so saves with the original keep its state")
        if original not in incompatible(info.get("dependencies")):
            problems.append(f'info.json: error: {name} replaces {original}, add "! {original}" to the dependencies')

    files = list(lua_files(mod))
    if migrates_from and (mod / "control.lua").is_file():
        # the helper itself mentions storage._migrated; a script has to require it or read the table by itself
        scripts = [path.read_text(encoding="utf-8", errors="replace") for path in files
                   if path.name != "migrated_storage.lua"]
        if not any("_migrated" in text or re.search(r"""require\s*\(?\s*["'][\w./]*migrated_storage["']""", text)
                   for text in scripts):
            problems.append("control.lua: error: migrates_from is set but no script takes storage._migrated; "
                            "copy lua/migrated_storage.lua of factorio-mod-tools and call take() in on_init and "
                            "on_configuration_changed")

    for path in files:
        if path.name == "migrated_storage.lua" and path.read_bytes() != HELPER.read_bytes():
            problems.append(f"{path.relative_to(mod)}: error: differs from lua/migrated_storage.lua of "
                            "factorio-mod-tools; copy it again")
    return problems


def main() -> int:
    mod = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    problems = check(mod)
    for problem in problems:
        print(problem)
    print(f"info.json: {len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
