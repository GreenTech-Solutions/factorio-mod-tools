#!/usr/bin/env python3
"""Resolve and download a mod's portal dependencies for the load action. Standard library only.

Required, "~" and "+" dependencies are followed recursively. Optional dependencies are left out unless named in
--extra-mods. The cache key is based on the resolved mod versions, not on the game version.

fetch reads FACTORIO_USERNAME and FACTORIO_TOKEN from the environment. The credentials are never printed.
"""
import argparse
import concurrent.futures
import glob
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

PORTAL = "https://mods.factorio.com"
RELEASES = "https://factorio.com/api/latest-releases"
BUILTIN = {"base", "space-age", "quality", "elevated-rails", "recycler"}
# a mod name may contain spaces ("Flare Stack"): it ends at the version comparison
DEPENDENCY = re.compile(r"^\s*(!|\?|\(\?\)|~|\+)?\s*(.+?)\s*(?:(<=|>=|<|>|=)\s*([\d.]+)\s*)?$")


def version_key(text):
    return tuple(int(part) for part in text.split("."))


def fail(message):
    sys.stderr.write("error: " + message + "\n")
    sys.exit(1)


def get_json(url, tries=4):
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "factorio-mod-tools-load"}), timeout=60) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            if error.code == 404:
                return None
            if attempt == tries - 1:
                fail("%s answered %d" % (url, error.code))
        except (urllib.error.URLError, TimeoutError, ConnectionError, json.JSONDecodeError) as error:
            if attempt == tries - 1:
                fail("cannot read %s: %s" % (url, error))
        time.sleep(2 * (attempt + 1))


def dependencies_of(info):
    for dependency in info.get("dependencies", []):
        match = DEPENDENCY.match(dependency)
        if match:
            yield match.groups()


def game_accepts(dependencies, game):
    """False when a release asks for a newer (or other) base than the game."""
    for prefix, name, operator, wanted in dependencies:
        if name != "base" or prefix in ("?", "(?)", "!") or not operator:
            continue
        have, want = version_key(game), version_key(wanted)
        want = want + (0,) * (3 - len(want))
        if (operator == ">=" and have < want) or (operator == ">" and have <= want) or (operator == "=" and have[:len(want)] != want):
            return False
    return True


def sha1_of(path):
    digest = hashlib.sha1()
    with open(path, "rb") as file:
        for block in iter(lambda: file.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


class Portal:
    def __init__(self, game):
        self.game = game
        self.minor = ".".join(game.split(".")[:2])
        self.cache = {}

    def newest(self, name):
        if name not in self.cache:
            data = get_json("%s/api/mods/%s/full" % (PORTAL, urllib.parse.quote(name)))
            best = None
            for release in (data or {}).get("releases", []):
                info = release.get("info_json", {})
                if info.get("factorio_version") != self.minor or not game_accepts(list(dependencies_of(info)), self.game):
                    continue
                if best is None or version_key(release["version"]) > version_key(best["version"]):
                    best = release
            self.cache[name] = None if best is None else {
                "name": name, "version": best["version"], "file_name": best["file_name"], "sha1": best["sha1"],
                "download_url": best["download_url"], "dependencies": best.get("info_json", {}).get("dependencies", []),
            }
        return self.cache[name]


def cmd_resolve(args):
    with open(args.info) as file:
        info = json.load(file)
    game = args.game
    if game == "stable":
        releases = get_json(RELEASES) or {}
        game = releases.get("stable", {}).get("headless")
        if not game:
            fail("no stable headless build in " + RELEASES)
    if not re.fullmatch(r"\d+\.\d+\.\d+", game):
        fail("game version must be 'stable' or a full version such as 2.1.24")
    source = Portal(game)
    chosen, missing = {}, set()

    def walk(wave):
        while wave:
            # one wave at a time so the portal can be asked in parallel
            with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
                found = dict(zip(sorted(wave), pool.map(source.newest, sorted(wave))))
            wave = set()
            for name, release in found.items():
                if release is None:
                    missing.add(name)
                    continue
                chosen[name] = release
                for prefix, dependency, _, _ in dependencies_of({"dependencies": release["dependencies"]}):
                    if prefix not in ("!", "?", "(?)") and dependency not in BUILTIN and dependency not in chosen and dependency not in missing:
                        wave.add(dependency)

    requested = [name.strip() for name in re.split(r"[\n,]+", args.extra_mods or "") if name.strip()]
    walk({name for prefix, name, _, _ in dependencies_of(info) if prefix not in ("!", "?", "(?)") and name not in BUILTIN})
    walk({name for name in requested if name not in BUILTIN and name not in chosen})
    if missing:
        fail("no release for game %s of: %s" % (game, ", ".join(sorted(missing))))
    mods = [{key: value for key, value in chosen[name].items() if key != "dependencies"} for name in sorted(chosen)]
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w") as file:
        json.dump({"game": game, "mods": mods}, file, indent=1)
        file.write("\n")
    print("%d mods for Factorio %s" % (len(mods), game))
    return 0


def read_lock(path):
    with open(path) as file:
        return json.load(file)


def download(entry, target, username, token):
    query = urllib.parse.urlencode({"username": username, "token": token})
    url = PORTAL + entry["download_url"] + "?" + query
    last = "unknown"
    for attempt in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "factorio-mod-tools-load"}), timeout=120) as response:
                with open(target + ".part", "wb") as file:
                    while True:
                        block = response.read(1 << 20)
                        if not block:
                            break
                        file.write(block)
            if entry.get("sha1") and sha1_of(target + ".part") != entry["sha1"]:
                last = "sha1 does not match"
                continue
            os.replace(target + ".part", target)
            return None
        except urllib.error.HTTPError as error:
            last = "the portal answered %d" % error.code
            if error.code in (401, 403):
                break  # the account or token is wrong: retrying does not help
        except (urllib.error.URLError, TimeoutError, ConnectionError) as error:
            last = type(error).__name__
        time.sleep(3 * (attempt + 1))
    if os.path.exists(target + ".part"):
        os.remove(target + ".part")
    return last


def cmd_fetch(args):
    lock = read_lock(args.lock)
    os.makedirs(args.dir, exist_ok=True)
    wanted = {entry["file_name"] for entry in lock["mods"]}
    for path in glob.glob(os.path.join(args.dir, "*")):
        if os.path.basename(path) not in wanted:
            os.remove(path)  # a version that is not in use any more: keeps the cache from growing
    todo = [entry for entry in lock["mods"] if not os.path.exists(os.path.join(args.dir, entry["file_name"]))]
    print("%d of %d mods in the cache, %d to download" % (len(lock["mods"]) - len(todo), len(lock["mods"]), len(todo)))
    if not todo:
        return 0
    username, token = os.environ.get("FACTORIO_USERNAME", ""), os.environ.get("FACTORIO_TOKEN", "")
    if not username:
        fail("FACTORIO_USERNAME is empty; set it to the account name that owns the player token")
    if not token:
        fail("FACTORIO_TOKEN is empty (the repository secret FACTORIO_PLAYER_TOKEN; a pull request from a fork gets no secrets)")
    # Check the account once so a wrong pair fails before downloading every mod.
    try:
        urllib.request.urlopen(urllib.request.Request(PORTAL + "/api/bookmarks?" + urllib.parse.urlencode({"username": username, "token": token}),
                                                      headers={"User-Agent": "factorio-mod-tools-load"}), timeout=60).close()
    except urllib.error.HTTPError as error:
        if error.code in (401, 403):
            fail("the mod portal rejected FACTORIO_USERNAME and FACTORIO_TOKEN (answer %d); use the account name and its player token, not a portal API key" % error.code)
        fail("the mod portal answered %d to the account check" % error.code)
    except (urllib.error.URLError, TimeoutError, ConnectionError) as error:
        fail("cannot reach the mod portal: " + type(error).__name__)
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda entry: download(entry, os.path.join(args.dir, entry["file_name"]), username, token), todo))
    failed = [(entry["name"], reason) for entry, reason in zip(todo, results) if reason]
    for name, reason in failed:
        sys.stderr.write("error: %s: %s\n" % (name, reason))
    if failed:
        if any("401" in reason or "403" in reason for _, reason in failed):
            sys.stderr.write("The portal refused the account. Use the account name that owns this player token.\n")
        return 1
    print("downloaded %d mods, %.0f MB in the cache" % (len(todo), sum(os.path.getsize(os.path.join(args.dir, e["file_name"])) for e in lock["mods"]) / 1e6))
    return 0


def cmd_key(args):
    # the same mods give the same key whatever the game version they were resolved for
    lines = ["%s %s %s" % (entry["name"], entry["version"], entry.get("sha1", "")) for entry in read_lock(args.lock)["mods"]]
    print(hashlib.sha256("\n".join(sorted(lines)).encode()).hexdigest()[:20])
    return 0


def cmd_game(args):
    print(read_lock(args.lock)["game"])
    return 0


def cmd_assemble(args):
    lock = read_lock(args.lock)
    with open(os.path.join(args.mod_path, "info.json")) as file:
        mod = json.load(file)
    mod_name = mod.get("name")
    if not mod_name:
        fail("mod info.json has no name")
    os.makedirs(args.out, exist_ok=True)
    for path in glob.glob(os.path.join(args.out, "*")):
        if os.path.islink(path) or os.path.isfile(path):
            os.remove(path)
    names = []
    for entry in lock["mods"]:
        source = os.path.join(args.cache, entry["file_name"])
        if not os.path.exists(source):
            fail("%s is missing; run fetch first" % source)
        os.symlink(os.path.abspath(source), os.path.join(args.out, entry["file_name"]))
        names.append(entry["name"])
    os.symlink(os.path.abspath(args.mod_path), os.path.join(args.out, mod_name))
    names.append(mod_name)
    builtins = ["base"]
    if int(lock["game"].split(".")[0]) >= 2:
        builtins.extend(["space-age", "quality", "elevated-rails", "recycler"])
    mods = [{"name": name, "enabled": True} for name in builtins + sorted(names)]
    with open(os.path.join(args.out, "mod-list.json"), "w") as file:
        json.dump({"mods": mods}, file, indent=1)
    print("mod-list.json: %s and %d portal mods" % (mod_name, len(lock["mods"])))
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    resolve = sub.add_parser("resolve")
    resolve.add_argument("--info", required=True)
    resolve.add_argument("--game", required=True)
    resolve.add_argument("--out", required=True)
    resolve.add_argument("--extra-mods", default="")
    resolve.set_defaults(run=cmd_resolve)
    fetch = sub.add_parser("fetch")
    fetch.add_argument("--lock", required=True)
    fetch.add_argument("--dir", required=True)
    fetch.set_defaults(run=cmd_fetch)
    key = sub.add_parser("key")
    key.add_argument("--lock", required=True)
    key.set_defaults(run=cmd_key)
    game = sub.add_parser("game")
    game.add_argument("--lock", required=True)
    game.set_defaults(run=cmd_game)
    assemble = sub.add_parser("assemble")
    assemble.add_argument("--lock", required=True)
    assemble.add_argument("--cache", required=True)
    assemble.add_argument("--mod-path", required=True)
    assemble.add_argument("--out", required=True)
    assemble.set_defaults(run=cmd_assemble)
    args = parser.parse_args()
    sys.exit(args.run(args))


if __name__ == "__main__":
    main()
