--!strict
-- Explicit setup only. No token values or gh diagnostics are printed or persisted.
local fs = require("@lune/fs")
local process = require("@lune/process")
local serde = require("@lune/serde")
local Similarity = require("./similarity")

assert(#process.args == 0, "usage: setup-similarity.luau")
local lock = Similarity.lock()
local root = Similarity.projectRoot()
local directory = ".tools/luau-similarity"

local function mkdir(path: string)
	assert(process.exec("/bin/mkdir", { path }).ok, "cannot create exclusively owned setup directory")
end

assert(process.exec("/bin/test", { "-L", ".tools" }).code == 1, "symlink tool parent is not permitted")
if fs.metadata(".tools").exists then
	Similarity.regular(".tools", "dir")
else
	mkdir(".tools")
end
assert(process.exec("/bin/test", { "-L", directory }).code == 1, "symlink installation is not permitted")
if fs.metadata(directory).exists then
	local ok = pcall(Similarity.verify)
	assert(ok, "existing installation is unverified; preserve it and inspect before retry")
	Similarity.regular(directory .. "/lune-types/fs.luau", "file")
	print("existing similarity installation verified; no writes or downloads")
	return
end
mkdir(directory)
fs.writeFile(
	directory .. "/setup-state.json",
	serde.encode("json", {
		schema = 1,
		lock_sha256 = serde.hash("sha256", fs.readFile("luau-similarity.lock.json")),
		state = "partial",
	})
)
local download = directory .. "/download"
mkdir(download)
local accessed, result = pcall(function()
	return process.exec("gh", {
		"release",
		"download",
		lock.tag,
		"--repo",
		"github.com/" .. lock.repository,
		"--pattern",
		lock.asset,
		"--dir",
		download,
	}, { env = { GH_HOST = "github.com" } })
end)
assert(
	accessed and result.ok,
	"private release access failed; check github.com authentication and permission; partial directory preserved"
)
local archive = download .. "/" .. lock.asset
Similarity.regular(archive, "file")
assert(
	serde.hash("sha256", fs.readFile(archive)) == lock.archive_sha256,
	"downloaded archive hash mismatch; partial directory preserved"
)
-- Only the exact approved hash is extracted into the new exclusively owned directory.
assert(process.exec("/usr/bin/tar", { "-xzf", archive, "-C", directory }).ok, "archive extraction failed")
Similarity.regular(directory .. "/luau-similarity", "file")
assert(
	serde.hash("sha256", fs.readFile(directory .. "/luau-similarity")) == lock.binary_sha256,
	"extracted binary hash mismatch"
)
assert(process.exec("/bin/chmod", { "700", directory .. "/luau-similarity" }).ok, "cannot set executable permission")

-- Lune embeds its editor types. Generate only in an owned temporary HOME/cwd, never the user's HOME.
local setupHome = directory .. "/type-home"
local setupCwd = directory .. "/type-setup"
mkdir(setupHome)
mkdir(setupCwd)
assert(
	process.exec("lune", { "setup" }, { cwd = root .. "/" .. setupCwd, env = { HOME = root .. "/" .. setupHome } }).ok,
	"local Lune type generation failed"
)
fs.move(setupHome .. "/.lune/.typedefs/0.10.5", directory .. "/lune-types", false)
fs.writeFile(directory .. "/lune-types/.luaurc", '{"aliases":{"lune":"."},"languageMode":"strict","lintErrors":true}\n')
fs.writeFile(
	directory .. "/installation.json",
	serde.encode("json", {
		schema = 1,
		lock_sha256 = serde.hash("sha256", fs.readFile("luau-similarity.lock.json")),
		binary_sha256 = lock.binary_sha256,
	})
)
Similarity.verify()
print(
	"similarity installed and verified; third-party notices retained, MPL source remains available with the same private Release"
)
