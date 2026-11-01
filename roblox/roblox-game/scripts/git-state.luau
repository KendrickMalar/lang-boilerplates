--!strict
local fs = require("@lune/fs")
local process = require("@lune/process")
local serde = require("@lune/serde")
local Similarity = require("./similarity")

export type Snapshot = { index: string, head: string, files: string, staged: string }
export type Update = { localRef: string, localSha: string, remoteRef: string, remoteSha: string }
local Git = {}

function Git.run(args: { string }): string
	local result = process.exec("git", args, { env = { GIT_OPTIONAL_LOCKS = "0" } })
	assert(result.ok, "Git metadata command failed; no source/index repair was attempted")
	return result.stdout
end

local function trim(value: string): string
	return (string.gsub(value, "%s+$", ""))
end

local function entries(value: string): { string }
	local out = {}
	for _, item in string.split(value, "\0") do
		if item ~= "" then
			table.insert(out, item)
		end
	end
	return out
end

function Git.validateFlags(value: string)
	for _, row in entries(value) do
		local flag = string.sub(row, 1, 1)
		assert(flag ~= "S" and not string.match(flag, "%l"), "hidden Git index flags are not permitted")
	end
end

local function sha(value: string): boolean
	return (#value == 40 or #value == 64) and string.match(value, "^[0-9a-f]+$") ~= nil
end

function Git.parseUpdates(value: string): { Update }
	local updates: { Update } = {}
	for _, line in string.split(value, "\n") do
		if line == "" then
			continue
		end
		local localRef, localSha, remoteRef, remoteSha = string.match(line, "^(%S+) (%S+) (%S+) (%S+)$")
		assert(localRef and localSha and remoteRef and remoteSha, "malformed push update")
		assert(sha(localSha) and sha(remoteSha), "invalid push SHA")
		assert(string.match(localSha, "[^0]"), "deletion push is not permitted")
		assert(
			sha(localRef)
				or localRef == "HEAD"
				or string.match(localRef, "^refs/heads/")
				or string.match(localRef, "^refs/tags/"),
			"unsupported local push ref"
		)
		assert(
			string.match(remoteRef, "^refs/heads/") or string.match(remoteRef, "^refs/tags/"),
			"unsupported remote push ref"
		)
		local update: Update =
			{ localRef = localRef, localSha = localSha, remoteRef = remoteRef, remoteSha = remoteSha }
		table.insert(updates, update)
	end
	assert(#updates > 0, "push requires explicit nonempty update refs")
	return updates
end

local REQUIRED = {
	"rokit.toml",
	"default.project.json",
	"wally.toml",
	"roblox.yml",
	"selene.toml",
	"stylua.toml",
	".luaurc",
	"scripts/.luaurc",
	"luau-similarity.lock.json",
	"scripts/check.sh",
	"scripts/test.luau",
	"scripts/similarity.luau",
	"scripts/verify-similarity.luau",
	"scripts/setup-similarity.luau",
	"scripts/check-git.luau",
	"scripts/test-helpers.luau",
	"scripts/git-state.luau",
	".husky/pre-commit",
	".husky/pre-push",
	"package.json",
	"pnpm-workspace.yaml",
	"pnpm-lock.yaml",
	"check-commit.mjs",
}

function Git.snapshot(push: boolean): Snapshot
	local root = Similarity.projectRoot()
	assert(trim(Git.run({ "rev-parse", "--show-toplevel" })) == root, "Git root differs from script project root")
	Git.validateFlags(Git.run({ "ls-files", "-v", "-z" }))
	assert(Git.run({ "diff", "--no-ext-diff", "--name-only", "-z" }) == "", "unstaged changes are not permitted")
	assert(Git.run({ "ls-files", "--others", "--exclude-standard", "-z" }) == "", "untracked files are not permitted")
	for _, path in
		entries(
			Git.run({ "ls-files", "--others", "--ignored", "--exclude-standard", "-z", "--", "src", "tests", "scripts" })
		)
	do
		assert(not string.match(path, "%.lua[u]?$"), "ignored runtime/helper source is not permitted")
	end
	local staged = Git.run({ "ls-files", "--stage", "-z" })
	local tracked: { [string]: boolean } = {}
	local hashes = {}
	for _, row in entries(staged) do
		local mode, _, stage, path = string.match(row, "^(%d+) ([0-9a-f]+) (%d)\t(.*)$")
		assert(mode and stage == "0" and path, "unmerged or unreadable Git index entry")
		assert(mode == "100644" or mode == "100755", "tracked symlinks/submodules are not supported by this gate")
		Similarity.regular(path, "file")
		tracked[path] = true
		table.insert(hashes, path .. "\0" .. serde.hash("sha256", fs.readFile(path)))
	end
	for _, required in REQUIRED do
		assert(tracked[required], "check input must be tracked/staged: " .. required)
	end
	local headResult = process.exec("git", { "rev-parse", "--verify", "HEAD" }, { env = { GIT_OPTIONAL_LOCKS = "0" } })
	local head = if headResult.ok then trim(headResult.stdout) else "UNBORN"
	if push then
		assert(head ~= "UNBORN", "push requires a resolvable HEAD")
		assert(
			Git.run({ "diff", "--no-ext-diff", "--cached", "--name-only", "-z" }) == "",
			"push requires clean HEAD/index"
		)
	end
	local index = trim(Git.run({ "rev-parse", "--git-path", "index" }))
	Similarity.regular(index, "file")
	return {
		index = serde.hash("sha256", fs.readFile(index)),
		head = head,
		files = serde.hash("sha256", table.concat(hashes, "\0")),
		staged = serde.hash("sha256", staged),
	}
end

function Git.validateUpdates(updates: { Update }, head: string)
	for _, update in updates do
		local named = trim(Git.run({ "rev-parse", "--verify", "--end-of-options", update.localRef .. "^{commit}" }))
		local supplied = trim(Git.run({ "rev-parse", "--verify", "--end-of-options", update.localSha .. "^{commit}" }))
		assert(named == head and supplied == head, "push ref differs from checked HEAD")
	end
end

function Git.equal(before: Snapshot, after: Snapshot)
	assert(
		before.head == after.head
			and before.index == after.index
			and before.staged == after.staged
			and before.files == after.files,
		"source or effective Git index changed during checks; no restoration attempted"
	)
end

return Git
