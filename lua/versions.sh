# shellcheck shell=bash disable=SC2034
# Pinned versions of the Lua check toolchain, sourced by lua/setup.sh and lua/check.sh.
# The CI cache key is the hash of this file: bump a version here and the toolchain is rebuilt.

# Factorio API the EmmyLua library is generated from (lua-api.factorio.com/<version>/)
factorio_api_version=2.1.20

hererocks_commit=5d77b0bafc8b96f82355ca2ce5637c00d78a065c
luacheck_version=1.2.0-1

emmylua_version=0.25.1
# sha256 of emmylua_check-<platform>.tar.gz from the EmmyLuaLs/emmylua-analyzer-rust release
emmylua_sha256_linux_x64=6ce2e19d0a82ed901c2c67a18567b340447682f843c7a0a82098e50e8d2f107e
emmylua_sha256_darwin_arm64=eeaad59d173cb8d7cb0fe778936d7b584fe114a3eb46587ef3e4aec24b605af4

# factoriomod-debug (fmtk) turns the API JSON into the EmmyLua library; run through npx, needs Node.js 22.7+
fmtk_version=2.1.9
