# factorio-mod-tools

Check and release tooling shared by the GreenTech-Solutions Factorio mods, so each mod keeps only its own settings.

| What | Where |
| --- | --- |
| Check: Lua 5.2 syntax, luacheck, `emmylua_check` against the Factorio API, `changelog.txt` format | `action.yml`, `lua/` |
| Release: semantic-release with semantic-release-factorio (version, `changelog.txt`, `info.json`, mod portal upload, GitHub release) | `release/action.yml`, `release/config.cjs` |
| The same check locally | `bin/factorio-mod-check` |

## Check

```yaml
# .github/workflows/check.yml
on:
  push:
    branches: [main]
  pull_request:
permissions:
  contents: read
jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
      - uses: GreenTech-Solutions/factorio-mod-tools@v1
        # with:
        #   path: my-mod    # when the mod is not at the repository root
```

What it runs, in order; every step runs, and the job fails if any of them fails:

1. `luac -p` of Lua 5.2 on every `.lua`: catches 5.3+ syntax (`//`, `&`, `|`, `~`, `<<`, `>>`) that the game rejects.
2. luacheck with [`lua/luacheckrc.lua`](lua/luacheckrc.lua). The mod's own `.luacheckrc` runs right after it, in the
   same environment, so it adds to the base tables:

   ```lua
   read_globals[#read_globals + 1] = "PlanetsLib"
   globals[#globals + 1] = "sounds"
   ignore[#ignore + 1] = "542"
   files["weather/paracelsin.lua"] = { ignore = { "211" } }
   ```

3. `emmylua_check --warnings-as-errors` with [`lua/emmyrc.json`](lua/emmyrc.json) merged with the mod's `.emmyrc.json`
   (objects merge, lists add up), against the EmmyLua library of the Factorio API version in
   [`lua/versions.sh`](lua/versions.sh). Catches fields and functions the game does not have.
4. [`lua/check-changelog.py`](lua/check-changelog.py): `changelog.txt` in the format the game parses. A changelog it
   cannot parse is dropped without a word in the log, and the in-game Changelog button stays grey.

The toolchain (Lua 5.2, luacheck, emmylua_check, the API library) is cached by the hash of `lua/versions.sh`.

## Release

```yaml
# .github/workflows/release.yml, next to the check job above
  release:
    needs: check
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    permissions:
      contents: write
      issues: write
      pull-requests: write
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          fetch-depth: 0
      - uses: GreenTech-Solutions/factorio-mod-tools/release@v1
        with:
          github-token: ${{ secrets.GITHUB_TOKEN }}
          factorio-token: ${{ secrets.FACTORIO_TOKEN }}
```

The mod needs no `package.json` or `.releaserc`: the action installs semantic-release from this repository and runs it
with `--extends release/config.cjs`. It releases from `main` or `master`, whichever exists. Commit types and the
`changelog.txt` sections they go to are in [`release/config.cjs`](release/config.cjs): `feat` is a minor release,
`fix`, `balance`, `compat`, `locale` and the rest are patches, and a breaking change is a major one. `FACTORIO_TOKEN` is
a mod portal API key with the upload permission.

## Locally

```bash
git clone https://github.com/GreenTech-Solutions/factorio-mod-tools.git
ln -s "$PWD/factorio-mod-tools/bin/factorio-mod-check" ~/.local/bin/
factorio-mod-check --setup     # once, and after a bump in lua/versions.sh; needs python3, curl, a C compiler, Node.js 22.7+
factorio-mod-check             # in a mod's directory, or: factorio-mod-check path/to/mod
```

The toolchain goes to `~/.local/share/factorio-lua` (`FACTORIO_LUA_HOME` to change it); `emmylua_check` is pinned for
Linux x64 and macOS arm64.

## Versions

Mods use the `v1` tag, which moves to the latest `v1.x.y`. A change that can make a passing mod fail (a stricter check,
a new API version) goes into a new minor version with a line in the release notes; a change of the inputs or of what the
mod has to provide gets `v2`. `.github/workflows/self-test.yml` runs the check on `test/good-mod` (must pass) and
`test/bad-mod` (must fail) and loads the release config with all its plugins.

Releases are made by release-please (`.github/workflows/release.yml`): a push to `master` with a `feat`, `fix`, `perf`,
`refactor` or `revert` commit opens a release PR (`!` makes a new major). Merging it tags `vX.Y.Z`, and the workflow moves
`v1` and `v1.Y` onto it; these two tags get no GitHub Release. Tags are not set by hand. A push that changes the tooling
(`action.yml`, `lua/`, `release/`, `publish/`, `bin/`, `package.json`) without a releasable commit fails. With a `PAT_TOKEN`
secret the release PR runs the self-test; with the default token it does not.
