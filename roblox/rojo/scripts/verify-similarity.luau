--!strict
local process = require("@lune/process")
local Similarity = require("./similarity")
local binary = Similarity.verify()
print("similarity verified")
if process.args[1] == "check" then
	assert(#process.args == 1, "usage: verify-similarity.luau [check]")
	local result = process.exec(
		binary,
		{ "src", "--threshold", "0.90", "--min-nodes", "50", "--fail-on-similar" },
		{ stdio = "inherit" }
	)
	process.exit(result.code)
end
assert(#process.args == 0, "usage: verify-similarity.luau [check]")
