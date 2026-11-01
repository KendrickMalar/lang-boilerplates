--!strict
-- Local verification only. Network access belongs to explicit setup, never this module.
local fs = require("@lune/fs")
local process = require("@lune/process")
local serde = require("@lune/serde")

export type Lock = {
	schema: number,
	repository: string,
	version: string,
	tag: string,
	target: string,
	asset: string,
	archive_sha256: string,
	binary_sha256: string,
	source_commit: string,
	mpl_source_asset: string,
	mpl_source_sha256: string,
}

local source = debug.info(1, "s")
local root = string.match(source, "^(.*)/scripts/similarity$")
assert(root ~= nil, "cannot locate similarity project root")
local Similarity = {}

function Similarity.projectRoot(): string
	assert(string.gsub(process.cwd, "/$", "") == root, "run from the script's own project root")
	return root :: string
end

function Similarity.regular(path: string, kind: string)
	-- Lune 0.10.5 metadata follows symlinks; use the macOS lstat-style test first.
	local link = process.exec("/bin/test", { "-L", path })
	assert(link.code == 1, "symlink or failed path inspection: " .. path)
	local meta = fs.metadata(path)
	assert(meta.kind ~= "symlink", "symlink is not permitted: " .. path)
	assert(meta.exists and meta.kind == kind, "similarity not installed or missing regular " .. kind .. ": " .. path)
end

function Similarity.readJson(path: string): any
	Similarity.regular(path, "file")
	local ok, data = pcall(function()
		return serde.decode("json", fs.readFile(path))
	end)
	assert(ok and type(data) == "table", "invalid similarity JSON")
	return data
end

local function hex(value: any, length: number): boolean
	return type(value) == "string" and #value == length and string.match(value, "^[0-9a-f]+$") ~= nil
end

function Similarity.lock(): Lock
	Similarity.projectRoot()
	local lock = Similarity.readJson("luau-similarity.lock.json")
	assert(lock.schema == 1 and lock.repository == "KendrickMalar/luau-similarity", "unsupported similarity lock")
	assert(
		type(lock.version) == "string" and string.match(lock.version, "^%d+%.%d+%.%d+$"),
		"invalid similarity version"
	)
	assert(lock.tag == "v" .. lock.version and lock.target == "aarch64-apple-darwin", "invalid similarity tag/target")
	assert(lock.asset == "luau-similarity-" .. lock.tag .. "-" .. lock.target .. ".tar.gz", "invalid similarity asset")
	assert(lock.mpl_source_asset == "luau-similarity-" .. lock.tag .. "-mpl-sources.tar.gz", "invalid MPL source asset")
	assert(hex(lock.archive_sha256, 64) and hex(lock.binary_sha256, 64), "invalid similarity hash")
	assert(hex(lock.mpl_source_sha256, 64) and hex(lock.source_commit, 40), "invalid similarity provenance")
	assert(process.os == "macos" and process.arch == "aarch64", "similarity supports Apple Silicon macOS only")
	return lock :: Lock
end

function Similarity.verify(): (string, Lock)
	local lock = Similarity.lock()
	Similarity.regular(".tools", "dir")
	Similarity.regular(".tools/luau-similarity", "dir")
	local binary = ".tools/luau-similarity/luau-similarity"
	Similarity.regular(binary, "file")
	assert(serde.hash("sha256", fs.readFile(binary)) == lock.binary_sha256, "similarity binary hash mismatch")
	local receipt = Similarity.readJson(".tools/luau-similarity/installation.json")
	assert(receipt.schema == 1 and receipt.binary_sha256 == lock.binary_sha256, "unowned similarity installation")
	assert(
		receipt.lock_sha256 == serde.hash("sha256", fs.readFile("luau-similarity.lock.json")),
		"installation lock hash mismatch"
	)
	local result = process.exec("./" .. binary, { "--version" })
	assert(
		result.ok and string.gsub(result.stdout, "%s+$", "") == "luau-similarity " .. lock.version,
		"similarity version/permission failure"
	)
	return "./" .. binary, lock
end

return Similarity
