--!strict
-- Pure helper tests only. Never invoke Git hooks or the complete check recursively.
local Git = require("./git-state")
local count = 0
local function rejects(callback: () -> ())
	assert(not pcall(callback), "invalid helper input was accepted")
	count += 1
end
local one = string.rep("1", 40)
local zero = string.rep("0", 40)
Git.validateFlags("H src/module.luau\0H scripts/test.luau\0")
count += 1
rejects(function()
	Git.validateFlags("h source\0")
end)
rejects(function()
	Git.validateFlags("S source\0")
end)
rejects(function()
	Git.validateFlags("s source\0")
end)
local updates = Git.parseUpdates("HEAD " .. one .. " refs/heads/main " .. zero .. "\n")
assert(
	#updates == 1 and updates[1].localSha == one and updates[1].remoteSha == zero,
	"valid push update was not preserved"
)
count += 1
rejects(function()
	Git.parseUpdates("")
end)
rejects(function()
	Git.parseUpdates("(delete) " .. zero .. " refs/heads/main " .. one .. "\n")
end)
rejects(function()
	Git.parseUpdates("HEAD bad refs/heads/main " .. zero .. "\n")
end)
rejects(function()
	Git.parseUpdates("HEAD " .. one .. " refs/notes/check " .. zero .. "\n")
end)
rejects(function()
	Git.parseUpdates("HEAD " .. one .. " refs/heads/main " .. zero .. " extra\n")
end)
print(`helper tests: {count} passed`)
