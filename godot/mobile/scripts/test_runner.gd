extends SceneTree
## Minimal runner: tests/**/test_*.gd extend RefCounted and define
## func test_*(t: TestContext) -> void. Zero tests, load failures and recorded failures exit 1.

const TEST_DIR: String = "res://tests"


func _initialize() -> void:
	var files: Array[String] = []
	_collect(TEST_DIR, files)
	files.sort()
	var passed: int = 0
	var failed: int = 0
	for path: String in files:
		var script: Script = load(path) as Script
		if script == null or not script.can_instantiate():
			failed += 1
			print("FAIL %s: cannot load test script" % path)
			continue
		var names: Array[String] = []
		for method: Dictionary in script.get_script_method_list():
			var method_name: String = method["name"]
			if method_name.begins_with("test_"):
				names.append(method_name)
		if names.is_empty():
			failed += 1
			print("FAIL %s: no test_* methods" % path)
			continue
		names.sort()
		var suite: Object = script.new()
		for method_name: String in names:
			var t: TestContext = TestContext.new()
			var result: Variant = suite.call(method_name, t)
			# A test that awaits returns early; failures recorded after the await would be lost.
			if result is Object and (result as Object).get_class() == "GDScriptFunctionState":
				failed += 1
				print("FAIL %s :: %s: await is not supported in tests" % [path, method_name])
				continue
			if t.failures.is_empty():
				passed += 1
				print("PASS %s :: %s" % [path, method_name])
			else:
				failed += 1
				for message: String in t.failures:
					print("FAIL %s :: %s: %s" % [path, method_name, message])
	print("%d passed, %d failed" % [passed, failed])
	if passed + failed == 0:
		print("FAIL no tests found under %s" % TEST_DIR)
		quit(1)
		return
	quit(1 if failed > 0 else 0)


func _collect(dir_path: String, out: Array[String]) -> void:
	var dir: DirAccess = DirAccess.open(dir_path)
	if dir == null:
		return
	for sub: String in dir.get_directories():
		_collect(dir_path.path_join(sub), out)
	for file: String in dir.get_files():
		if file.begins_with("test_") and file.ends_with(".gd"):
			out.append(dir_path.path_join(file))
