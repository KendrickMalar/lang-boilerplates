--!strict
local process = require("@lune/process")
local stdio = require("@lune/stdio")
local Git = require("./git-state")

local mode = process.args[1]
assert(#process.args == 1 and (mode == "commit" or mode == "push"), "usage: check-git.luau commit|push")
local push = mode == "push"
local updates = if push then Git.parseUpdates(stdio.readToEnd()) else {}
local before = Git.snapshot(push)
if push then
	Git.validateUpdates(updates, before.head)
end
local result = process.exec("sh", { "scripts/check.sh", "all" }, { stdio = "inherit" })
if not result.ok then
	process.exit(result.code)
end
local after = Git.snapshot(push)
Git.equal(before, after)
if push then
	Git.validateUpdates(updates, after.head)
end
print("Git source/index guard verified; no automatic staging or restoration")
