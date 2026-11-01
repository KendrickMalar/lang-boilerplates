--!strict
-- Dependency-direction check for the layers declared in architecture.json. Reads files only.
-- usage: lune run scripts/check-architecture.luau architecture.json sourcemap.json
local fs = require("@lune/fs")
local process = require("@lune/process")
local serde = require("@lune/serde")

type Token = { kind: string, value: string, line: number }
type Step = { parent: boolean, name: string }
type Path = { root: string, steps: { Step } }
type Def = { index: number, name: string, path: Path? }
type Layer = {
	name: string,
	path: string,
	mayRequire: { [string]: boolean },
	acyclic: boolean,
	modules: boolean,
	forbiddenServices: { [string]: boolean },
}
type Boot = { path: string, kind: string, max: number, count: number }
type Rules = {
	architecture: string,
	sourceRoot: string,
	packagesPath: string,
	packagesInstance: { string },
	layers: { Layer },
	boots: { Boot },
}
type Node = { name: string, parent: Node?, children: { Node }, file: string? }
type Resolved = { file: string?, packages: boolean, problem: string? }

local PACKAGES = "packages"
local violations: { string } = {}

local function fail(message: string): never
	error("architecture: " .. message, 0)
end

local function violation(file: string, line: number, message: string)
	table.insert(violations, `architecture: {file}:{line}: {message}`)
end

-- Paths ---------------------------------------------------------------------

-- Collapses "." and ".." segments. Returns nil when the path escapes the project root.
local function normalize(path: string): string?
	local out: { string } = {}
	for segment in string.gmatch(path, "[^/]+") do
		if segment == ".." then
			if #out == 0 then
				return nil
			end
			table.remove(out)
		elseif segment ~= "." then
			table.insert(out, segment)
		end
	end
	return table.concat(out, "/")
end

local function dirname(path: string): string
	return string.match(path, "^(.*)/[^/]*$") or ""
end

local function basename(path: string): string
	return string.match(path, "([^/]*)$") or path
end

local function join(base: string, rest: string): string?
	if base == "" then
		return normalize(rest)
	end
	return normalize(base .. "/" .. rest)
end

local function within(path: string, prefix: string): boolean
	return path == prefix or string.sub(path, 1, #prefix + 1) == prefix .. "/"
end

local function scriptKind(path: string): string?
	return string.match(basename(path), "^.+%.(server)%.luau?$")
		or string.match(basename(path), "^.+%.(client)%.luau?$")
end

-- Rules ---------------------------------------------------------------------

local function object(value: any, allowed: { string }, where: string): any
	if type(value) ~= "table" then
		fail(`{where} must be an object`)
	end
	local known: { [string]: boolean } = {}
	for _, key in allowed do
		known[key] = true
	end
	for key in value do
		if type(key) ~= "string" or not known[key] then
			fail(`unknown key {key} in {where}`)
		end
	end
	return value
end

local function text(value: any, where: string): string
	if type(value) ~= "string" or value == "" then
		fail(`{where} must be a non-empty string`)
	end
	return value
end

local function list(value: any, where: string): { string }
	if type(value) ~= "table" then
		fail(`{where} must be an array of strings`)
	end
	local out: { string } = {}
	for index, item in value do
		if type(index) ~= "number" then
			fail(`{where} must be an array of strings`)
		end
		table.insert(out, text(item, where))
	end
	return out
end

local function cleanPath(value: any, where: string): string
	local path = normalize(text(value, where))
	if path == nil or path == "" then
		fail(`{where} must stay inside the project`)
	end
	return path :: string
end

local function loadRules(path: string): Rules
	if not fs.isFile(path) then
		fail(`missing {path}; copy architecture/<option>.json to {path}`)
	end
	local ok, decoded = pcall(serde.decode, "json" :: any, fs.readFile(path))
	if not ok then
		fail(`{path} is not valid JSON: {decoded}`)
	end
	local raw = object(decoded, { "schema", "architecture", "sourceRoot", "packages", "layers", "bootScripts" }, path)
	if raw.schema ~= 1 then
		fail(`{path}: schema must be 1`)
	end
	local packages = object(raw.packages, { "path", "instance" }, "packages")
	local rules: Rules = {
		architecture = text(raw.architecture, "architecture"),
		sourceRoot = cleanPath(raw.sourceRoot, "sourceRoot"),
		packagesPath = cleanPath(packages.path, "packages.path"),
		packagesInstance = list(packages.instance, "packages.instance"),
		layers = {},
		boots = {},
	}
	local names: { [string]: boolean } = { [PACKAGES] = true }
	if type(raw.layers) ~= "table" or #raw.layers == 0 then
		fail("layers must be a non-empty array")
	end
	for index, item in raw.layers do
		local where = `layers[{index}]`
		local layer = object(item, { "name", "path", "mayRequire", "acyclic", "modules", "forbiddenServices" }, where)
		local name = text(layer.name, where .. ".name")
		if names[name] then
			fail(`duplicate layer name {name}`)
		end
		names[name] = true
		local layerPath = cleanPath(layer.path, where .. ".path")
		if not within(layerPath, rules.sourceRoot) then
			fail(`{where}.path must be inside sourceRoot`)
		end
		local may: { [string]: boolean } = {}
		for _, target in list(layer.mayRequire, where .. ".mayRequire") do
			may[target] = true
		end
		local services: { [string]: boolean } = {}
		for _, service in list(layer.forbiddenServices or {}, where .. ".forbiddenServices") do
			services[service] = true
		end
		for _, flag in { "acyclic", "modules" } do
			if layer[flag] ~= nil and type(layer[flag]) ~= "boolean" then
				fail(`{where}.{flag} must be a boolean`)
			end
		end
		table.insert(rules.layers, {
			name = name,
			path = layerPath,
			mayRequire = may,
			acyclic = layer.acyclic == true,
			modules = layer.modules ~= false,
			forbiddenServices = services,
		})
	end
	for _, layer in rules.layers do
		for target in layer.mayRequire do
			if not names[target] then
				fail(`layer {layer.name} may require unknown layer {target}`)
			end
		end
	end
	-- The deepest layer wins, so "src/server/services" is matched before "src/server".
	table.sort(rules.layers, function(a: Layer, b: Layer): boolean
		return #a.path > #b.path
	end)
	if raw.bootScripts ~= nil and type(raw.bootScripts) ~= "table" then
		fail("bootScripts must be an array")
	end
	for index, item in raw.bootScripts or {} do
		local where = `bootScripts[{index}]`
		local boot = object(item, { "path", "kind", "max" }, where)
		local kind = text(boot.kind, where .. ".kind")
		if kind ~= "server" and kind ~= "client" then
			fail(`{where}.kind must be server or client`)
		end
		if type(boot.max) ~= "number" or boot.max < 0 then
			fail(`{where}.max must be a non-negative number`)
		end
		table.insert(
			rules.boots,
			{ path = cleanPath(boot.path, where .. ".path"), kind = kind, max = boot.max, count = 0 }
		)
	end
	return rules
end

local function layerOf(rules: Rules, path: string): Layer?
	for _, layer in rules.layers do
		if within(path, layer.path) then
			return layer
		end
	end
	return nil
end

-- Sourcemap -----------------------------------------------------------------

local function buildTree(data: any, parent: Node?, byFile: { [string]: Node }): Node
	local node: Node = { name = tostring(data.name), parent = parent, children = {}, file = nil }
	if type(data.filePaths) == "table" then
		for _, raw in data.filePaths do
			local path = type(raw) == "string" and normalize(raw) or nil
			if path and (string.match(path, "%.luau$") or string.match(path, "%.lua$")) then
				node.file = path
				byFile[path] = node
			end
		end
	end
	if type(data.children) == "table" then
		for _, child in data.children do
			table.insert(node.children, buildTree(child, node, byFile))
		end
	end
	return node
end

local function instancePath(node: Node): { string }
	local names: { string } = {}
	local current: Node? = node
	while current and current.parent do
		table.insert(names, 1, current.name)
		current = current.parent
	end
	return names
end

local function startsWith(names: { string }, prefix: { string }): boolean
	if #names < #prefix then
		return false
	end
	for index, name in prefix do
		if names[index] ~= name then
			return false
		end
	end
	return true
end

-- Tokenizer -----------------------------------------------------------------

local ESCAPES: { [string]: string } = { n = "\n", t = "\t", ["\\"] = "\\", ['"'] = '"', ["'"] = "'" }
local SYMBOLS3 = { ["..."] = true, ["//="] = true, ["..="] = true }
local SYMBOLS2 = {}
for _, symbol in { "::", "..", "==", "~=", "<=", ">=", "->", "+=", "-=", "*=", "/=", "%=", "^=", "//" } do
	SYMBOLS2[symbol] = true
end

local function countLines(source: string): number
	local _, count = string.gsub(source, "\n", "")
	return count
end

local function tokenize(source: string, file: string): { Token }
	local tokens: { Token } = {}
	local i, line, n = 1, 1, #source
	local function longLevel(at: number): number?
		local eq = string.match(source, "^%[(=*)%[", at)
		return if eq then #eq else nil
	end
	local function skipLong(at: number, level: number): (number, string)
		local open = at + level + 2
		local first, last = string.find(source, "]" .. string.rep("=", level) .. "]", open, true)
		if not first or not last then
			fail(`{file}:{line}: unterminated long bracket`)
		end
		line += countLines(string.sub(source, at, last :: number))
		return (last :: number) + 1, string.sub(source, open, (first :: number) - 1)
	end
	while i <= n do
		local c = string.sub(source, i, i)
		local startLine = line
		if c == "\n" then
			line += 1
			i += 1
		elseif string.match(c, "%s") then
			i += 1
		elseif string.sub(source, i, i + 1) == "--" then
			local level = longLevel(i + 2)
			if level then
				i = skipLong(i + 2, level)
			else
				i = string.find(source, "\n", i, true) or n + 1
			end
		elseif c == '"' or c == "'" or c == "`" then
			local parts: { string } = {}
			local kind = "string"
			local j = i + 1
			local closed = false
			while j <= n do
				local d = string.sub(source, j, j)
				if d == "\\" then
					local e = string.sub(source, j + 1, j + 1)
					if ESCAPES[e] then
						table.insert(parts, ESCAPES[e])
					else
						kind = "dynamic"
					end
					if e == "\n" then
						line += 1
					end
					j += 2
				elseif d == c then
					closed = true
					break
				elseif d == "\n" and c ~= "`" then
					break
				else
					if d == "\n" then
						line += 1
					elseif c == "`" and d == "{" then
						-- Interpolation: skip to the matching brace; the string is not a literal path.
						kind = "dynamic"
						local depth = 0
						while j <= n do
							local e = string.sub(source, j, j)
							if e == "{" then
								depth += 1
							elseif e == "}" then
								depth -= 1
								if depth == 0 then
									break
								end
							elseif e == "\n" then
								line += 1
							end
							j += 1
						end
					end
					table.insert(parts, d)
					j += 1
				end
			end
			if not closed then
				fail(`{file}:{startLine}: unterminated string`)
			end
			table.insert(tokens, { kind = kind, value = table.concat(parts), line = startLine })
			i = j + 1
		elseif c == "[" and longLevel(i) then
			local nextIndex, content = skipLong(i, longLevel(i) :: number)
			table.insert(tokens, { kind = "string", value = content, line = startLine })
			i = nextIndex
		elseif string.match(c, "[%a_]") then
			local word = string.match(source, "^[%w_]+", i) :: string
			table.insert(tokens, { kind = "name", value = word, line = line })
			i += #word
		elseif string.match(c, "%d") or (c == "." and string.match(string.sub(source, i + 1, i + 1), "%d")) then
			local number = string.match(source, "^0[xXbB][%x_]+", i)
				or string.match(source, "^[%d_]*%.?[%d_]*[eE][%+%-]?[%d_]+", i)
				or string.match(source, "^[%d_]*%.?[%d_]+", i)
				or c
			table.insert(tokens, { kind = "number", value = number, line = line })
			i += #number
		else
			local three, two = string.sub(source, i, i + 2), string.sub(source, i, i + 1)
			local symbol = if SYMBOLS3[three] then three elseif SYMBOLS2[two] then two else c
			table.insert(tokens, { kind = "symbol", value = symbol, line = line })
			i += #symbol
		end
	end
	return tokens
end

local function isSymbol(token: Token?, value: string): boolean
	return token ~= nil and token.kind == "symbol" and token.value == value
end

-- Instance paths --------------------------------------------------------------

local CHILD_METHODS = { WaitForChild = true, FindFirstChild = true, GetService = true }

-- Parses script/game/<local> followed by .Name, ["Name"], :WaitForChild("Name"[, n]),
-- :FindFirstChild("Name") or game:GetService("Name"). Stops at the first other token.
local function parsePath(tokens: { Token }, start: number, lookup: (string, number) -> Path?): (Path?, number)
	local first = tokens[start]
	if not first or first.kind ~= "name" then
		return nil, start
	end
	local path: Path
	if first.value == "script" or first.value == "game" then
		path = { root = first.value, steps = {} }
	else
		local found = lookup(first.value, start)
		if not found then
			return nil, start
		end
		path = { root = found.root, steps = table.clone(found.steps) }
	end
	local i = start + 1
	while true do
		local a, b = tokens[i], tokens[i + 1]
		if isSymbol(a, ".") and b and b.kind == "name" then
			table.insert(path.steps, { parent = b.value == "Parent", name = b.value })
			i += 2
		elseif isSymbol(a, "[") and b and b.kind == "string" and isSymbol(tokens[i + 2], "]") then
			table.insert(path.steps, { parent = false, name = b.value })
			i += 3
		elseif
			isSymbol(a, ":")
			and b
			and CHILD_METHODS[b.value]
			and isSymbol(tokens[i + 2], "(")
			and tokens[i + 3]
			and tokens[i + 3].kind == "string"
		then
			local j = i + 4
			if
				b.value == "WaitForChild"
				and isSymbol(tokens[j], ",")
				and tokens[j + 1]
				and tokens[j + 1].kind == "number"
			then
				j += 2
			end
			if not isSymbol(tokens[j], ")") then
				break
			end
			if b.value == "GetService" and (path.root ~= "game" or #path.steps > 0) then
				break
			end
			table.insert(path.steps, { parent = false, name = tokens[i + 3].value })
			i = j + 1
		else
			break
		end
	end
	return path, i
end

local function continues(token: Token?): boolean
	if token == nil then
		return false
	end
	if token.kind == "string" or token.kind == "dynamic" then
		return true
	end
	return token.kind == "symbol"
		and (token.value == "." or token.value == ":" or token.value == "[" or token.value == "(" or token.value == "{")
end

-- Records `local name = <instance path>` so `require(Name.Child)` can be resolved.
-- Scope is ignored: the latest preceding definition of a name wins.
local function collectDefs(tokens: { Token }): (string, number) -> Path?
	local defs: { Def } = {}
	local function lookup(name: string, before: number): Path?
		for index = #defs, 1, -1 do
			local def = defs[index]
			if def.index < before and def.name == name then
				return def.path
			end
		end
		return nil
	end
	for k, token in tokens do
		if token.kind ~= "name" or token.value ~= "local" then
			continue
		end
		local j = k + 1
		local names: { string } = {}
		while tokens[j] and tokens[j].kind == "name" and tokens[j].value ~= "function" do
			table.insert(names, tokens[j].value)
			j += 1
			if isSymbol(tokens[j], ":") then
				local depth = 0
				while tokens[j] do
					local t = tokens[j]
					if t.kind == "symbol" and (t.value == "(" or t.value == "{" or t.value == "<") then
						depth += 1
					elseif t.kind == "symbol" and (t.value == ")" or t.value == "}" or t.value == ">") then
						depth -= 1
					elseif depth == 0 and t.kind == "symbol" and (t.value == "," or t.value == "=") then
						break
					end
					j += 1
				end
			end
			if isSymbol(tokens[j], ",") then
				j += 1
			else
				break
			end
		end
		local path: Path? = nil
		if #names == 1 and isSymbol(tokens[j], "=") then
			local parsed, stop = parsePath(tokens, j + 1, lookup)
			if parsed and not continues(tokens[stop]) then
				path = parsed
			end
		end
		for _, name in names do
			table.insert(defs, { index = k, name = name, path = path })
		end
	end
	return lookup
end

-- Resolution -----------------------------------------------------------------

local luaurcCache: { [string]: { [string]: string } } = {}

local function aliasesAt(dir: string): { [string]: string }
	local cached = luaurcCache[dir]
	if cached then
		return cached
	end
	local aliases: { [string]: string } = {}
	local file = if dir == "" then ".luaurc" else dir .. "/.luaurc"
	if fs.isFile(file) then
		local ok, data = pcall(serde.decode, "json" :: any, fs.readFile(file))
		if ok and type(data) == "table" and type(data.aliases) == "table" then
			for name, target in data.aliases do
				if type(name) == "string" and type(target) == "string" then
					aliases[string.lower(name)] = join(dir, target) or ""
				end
			end
		end
	end
	luaurcCache[dir] = aliases
	return aliases
end

local function findAlias(dir: string, name: string): string?
	local current = dir
	while true do
		local target = aliasesAt(current)[string.lower(name)]
		if target then
			return target
		end
		if current == "" then
			return nil
		end
		current = dirname(current)
	end
end

local function resolveFile(rules: Rules, base: string?): Resolved
	if base == nil then
		return { packages = false, problem = "path escapes the project root" }
	end
	local path = base :: string
	if within(path, rules.packagesPath) then
		return { packages = true }
	end
	for _, candidate in { path .. ".luau", path .. ".lua", path .. "/init.luau", path .. "/init.lua" } do
		if fs.isFile(candidate) then
			return { file = candidate, packages = false }
		end
	end
	return { packages = false, problem = `cannot resolve {path}` }
end

local function resolveString(rules: Rules, file: string, spec: string): Resolved
	local dir = dirname(file)
	local isInit = string.match(basename(file), "^init%.") ~= nil
	if string.sub(spec, 1, 2) == "./" or string.sub(spec, 1, 3) == "../" then
		-- An init file stands for its directory, so ./ is relative to the directory's parent.
		return resolveFile(rules, join(if isInit then dirname(dir) else dir, spec))
	end
	local alias, rest = string.match(spec, "^@([^/]+)/?(.*)$")
	if alias == nil or rest == nil then
		return { packages = false, problem = `cannot resolve "{spec}": use ./, ../ or an alias` }
	end
	if alias == "self" then
		if not isInit then
			return { packages = false, problem = `cannot resolve "{spec}": @self is checked only in init files` }
		end
		return resolveFile(rules, join(dir, rest))
	end
	local target = findAlias(dir, alias)
	if target == nil then
		return { packages = false, problem = `cannot resolve "{spec}": unknown alias @{alias}` }
	end
	return resolveFile(rules, join(target, rest))
end

local function resolvePath(rules: Rules, root: Node, byFile: { [string]: Node }, file: string, path: Path): Resolved
	local node: Node
	if path.root == "script" then
		local own = byFile[file]
		if own == nil then
			return { packages = false, problem = `cannot resolve script: {file} is not in the sourcemap` }
		end
		node = own
	else
		node = root
	end
	local names = instancePath(node)
	local missing = false
	for _, step in path.steps do
		if step.parent then
			if missing or node.parent == nil then
				return { packages = false, problem = "cannot resolve .Parent above the DataModel" }
			end
			node = node.parent :: Node
			table.remove(names)
		else
			table.insert(names, step.name)
			if not missing then
				local found: Node? = nil
				for _, child in node.children do
					if child.name == step.name then
						found = child
						break
					end
				end
				if found then
					node = found
				else
					missing = true
				end
			end
		end
	end
	if startsWith(names, rules.packagesInstance) then
		return { packages = true }
	end
	local joined = table.concat(names, ".")
	if missing then
		return { packages = false, problem = `cannot resolve instance {joined}` }
	end
	if node.file == nil then
		return { packages = false, problem = `{joined} has no source file` }
	end
	return { file = node.file, packages = false }
end

-- Main ------------------------------------------------------------------------

local function collectSources(dir: string, out: { string })
	local names = fs.readDir(dir)
	table.sort(names)
	for _, name in names do
		local path = dir .. "/" .. name
		if fs.isDir(path) then
			collectSources(path, out)
		elseif string.match(name, "%.luau$") or string.match(name, "%.lua$") then
			table.insert(out, path)
		end
	end
end

if #process.args ~= 2 then
	fail("usage: check-architecture.luau <architecture.json> <sourcemap.json>")
end
local rules = loadRules(process.args[1])
local sourcemapPath = process.args[2]
if not fs.isFile(sourcemapPath) then
	fail(`missing {sourcemapPath}; run rojo sourcemap first`)
end
local okMap, map = pcall(serde.decode, "json" :: any, fs.readFile(sourcemapPath))
if not okMap or type(map) ~= "table" then
	fail(`{sourcemapPath} is not valid JSON`)
end
local byFile: { [string]: Node } = {}
local tree = buildTree(map, nil, byFile)

if not fs.isDir(rules.sourceRoot) then
	fail(`missing source root {rules.sourceRoot}`)
end
local files: { string } = {}
collectSources(rules.sourceRoot, files)

local edges: { [string]: { string } } = {}
local fileLayer: { [string]: Layer } = {}
local requireCount = 0

for _, file in files do
	local layer = layerOf(rules, file)
	if layer == nil then
		violation(file, 1, "file is not in any layer of architecture.json")
		continue
	end
	local own = layer :: Layer
	fileLayer[file] = own
	local kind = scriptKind(file)
	if kind then
		local matched = false
		for _, boot in rules.boots do
			if boot.kind == kind and boot.path == dirname(file) then
				matched = true
				boot.count += 1
				if boot.count > boot.max then
					violation(file, 1, `at most {boot.max} boot script(s) of kind {kind} in {boot.path}`)
				end
			end
		end
		if not matched then
			local allowed: { string } = {}
			for _, boot in rules.boots do
				if boot.kind == kind then
					table.insert(allowed, boot.path)
				end
			end
			violation(file, 1, `{kind} boot script outside {table.concat(allowed, ", ")}`)
		end
	elseif not own.modules then
		violation(file, 1, `ModuleScripts are not allowed in {own.name}; move it into a deeper layer`)
	end

	local tokens = tokenize(fs.readFile(file), file)
	local lookup = collectDefs(tokens)
	for k, token in tokens do
		if token.kind ~= "name" then
			continue
		end
		if token.value == "GetService" and isSymbol(tokens[k - 1], ":") and isSymbol(tokens[k + 1], "(") then
			local service = tokens[k + 2]
			if service and service.kind == "string" and own.forbiddenServices[service.value] then
				violation(file, token.line, `{own.name} must not use {service.value}`)
			end
		elseif token.value == "game" and isSymbol(tokens[k + 1], ".") then
			local service = tokens[k + 2]
			if service and service.kind == "name" and own.forbiddenServices[service.value] then
				violation(file, token.line, `{own.name} must not use {service.value}`)
			end
		end
		if token.value ~= "require" or isSymbol(tokens[k - 1], ".") or isSymbol(tokens[k - 1], ":") then
			continue
		end
		local resolved: Resolved
		local nextToken = tokens[k + 1]
		if nextToken and nextToken.kind == "string" then
			resolved = resolveString(rules, file, nextToken.value)
		elseif isSymbol(nextToken, "(") then
			local depth, close = 0, nil
			for j = k + 1, #tokens do
				local t = tokens[j]
				if t.kind == "symbol" and (t.value == "(" or t.value == "[" or t.value == "{") then
					depth += 1
				elseif t.kind == "symbol" and (t.value == ")" or t.value == "]" or t.value == "}") then
					depth -= 1
					if depth == 0 then
						close = j
						break
					end
				end
			end
			if close == nil then
				violation(file, token.line, "unterminated require call")
				continue
			end
			local arg = tokens[k + 2]
			if close == k + 3 and arg.kind == "string" then
				resolved = resolveString(rules, file, arg.value)
			else
				local path, stop = parsePath(tokens, k + 2, lookup)
				if path == nil or stop ~= close then
					violation(
						file,
						token.line,
						"dynamic require cannot be checked; use a string or a fixed instance path"
					)
					continue
				end
				resolved = resolvePath(rules, tree, byFile, file, path :: Path)
			end
		else
			violation(file, token.line, "require used as a value cannot be checked; call it directly")
			continue
		end
		requireCount += 1
		if resolved.problem then
			violation(file, token.line, resolved.problem :: string)
			continue
		end
		local targetName: string
		local targetFile = resolved.file
		if resolved.packages then
			targetName = PACKAGES
		else
			local targetLayer = layerOf(rules, targetFile :: string)
			if targetLayer == nil then
				violation(file, token.line, `{targetFile} is outside every layer`)
				continue
			end
			targetName = (targetLayer :: Layer).name
		end
		if not own.mayRequire[targetName] then
			local suffix = if targetFile then ` ({targetFile})` else ""
			violation(file, token.line, `{own.name} must not require {targetName}{suffix}`)
		elseif targetFile and own.acyclic and targetName == own.name then
			edges[file] = edges[file] or {}
			table.insert(edges[file], targetFile :: string)
		end
	end
end

-- Cycles inside acyclic layers (e.g. services must receive each other through Start(deps)).
local state: { [string]: number } = {}
local stack: { string } = {}
local function visit(file: string)
	state[file] = 1
	table.insert(stack, file)
	local targets: { string } = edges[file] or {}
	for _, target in targets do
		if state[target] == 1 then
			local cycle: { string } = {}
			local recording = false
			for _, entry in stack do
				if entry == target then
					recording = true
				end
				if recording then
					table.insert(cycle, entry)
				end
			end
			table.insert(cycle, target)
			violation(file, 1, `dependency cycle in {fileLayer[file].name}: {table.concat(cycle, " -> ")}`)
		elseif state[target] == nil then
			visit(target)
		end
	end
	table.remove(stack)
	state[file] = 2
end
for _, file in files do
	if state[file] == nil and edges[file] then
		visit(file)
	end
end

for _, line in violations do
	print(line)
end
print(`architecture: {rules.architecture}: {#files} files, {requireCount} requires, {#violations} violations`)
if #violations > 0 then
	process.exit(1)
end
