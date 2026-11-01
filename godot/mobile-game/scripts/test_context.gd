class_name TestContext
extends RefCounted
## Collects failures for one test method. GDScript has no exceptions, so tests record them.

var failures: Array[String] = []


func expect(condition: bool, message: String) -> void:
	if not condition:
		failures.append(message)


func expect_eq(actual: Variant, expected: Variant, message: String = "") -> void:
	if typeof(actual) == typeof(expected) and actual == expected:
		return
	var prefix: String = message + ": " if message != "" else ""
	failures.append("%sexpected %s, got %s" % [prefix, var_to_str(expected), var_to_str(actual)])
