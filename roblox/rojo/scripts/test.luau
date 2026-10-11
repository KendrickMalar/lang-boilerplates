-- Minimal Lune runner: every tests/**/*.spec.luau returns { [name]: () -> () }.
local fs = require("@lune/fs")
local process = require("@lune/process")

local SUFFIX = ".spec.luau"

local function collect(dir: string, out: { string })
	if not fs.isDir(dir) then
		return
	end
	local names = fs.readDir(dir)
	table.sort(names)
	for _, name in names do
		local path = dir .. "/" .. name
		if fs.isDir(path) then
			collect(path, out)
		elseif string.sub(name, -#SUFFIX) == SUFFIX then
			table.insert(out, path)
		end
	end
end

local files = {}
collect("tests", files)
local passed, failed = 0, 0
for _, file in files do
	-- Paths resolve relative to this script; the extension is omitted.
	local modulePath = "../" .. string.sub(file, 1, -#".luau" - 1)
	local loaded, suite = pcall(function()
		return require(modulePath)
	end)
	if not loaded or type(suite) ~= "table" then
		failed += 1
		print(`FAIL {file}: spec must return a table of test functions ({suite})`)
		continue
	end
	local names = {}
	for name in suite do
		if type(name) == "string" then
			table.insert(names, name)
		else
			failed += 1
			print(`FAIL {file} :: {name}: test names must be strings`)
		end
	end
	if next(suite) == nil then
		failed += 1
		print(`FAIL {file}: no tests in spec`)
	end
	table.sort(names)
	for _, name in names do
		local ok, err = pcall(suite[name])
		if ok then
			passed += 1
			print(`PASS {file} :: {name}`)
		else
			failed += 1
			print(`FAIL {file} :: {name}: {err}`)
		end
	end
end
print(`{passed} passed, {failed} failed`)
if passed + failed == 0 then
	print("error: no tests discovered")
	process.exit(1)
end
if failed > 0 then
	process.exit(1)
end
