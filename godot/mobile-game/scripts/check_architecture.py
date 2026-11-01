"""Check Godot layer dependencies against a rules file (stdlib only, Python 3.9+).

Usage: python3 scripts/check_architecture.py [--root DIR] [RULES]
Exit codes: 0 no violations, 1 violations, 2 usage or configuration error.
"""
import argparse
import json
import posixpath
import re
import sys
from pathlib import Path

SCANNED = (".gd", ".tscn", ".tres")
EXTENDS = re.compile(r"\bextends\s+([A-Za-z_][\w.]*)")
CLASS_NAME = re.compile(r"^\s*class_name\s+([A-Za-z_]\w*)", re.MULTILINE)
RESOURCE_PATH = re.compile(r"""\bpath\s*=\s*"(res://[^"]*)\"""")
RESOURCE_UID = re.compile(r"""\buid\s*=\s*"(uid://[^"]*)\"""")
AUTOLOAD = re.compile(r"""^\s*([A-Za-z_]\w*)\s*=\s*"\*?(res://[^"]*)"\s*$""")


class ConfigError(Exception):
    pass


def split_gdscript(text):
    """Return (code with strings and comments blanked, [(offset, string value)])."""
    code = list(text)
    strings = []
    i = 0
    length = len(text)
    while i < length:
        char = text[i]
        if char == "#":
            end = text.find("\n", i)
            end = length if end < 0 else end
            for j in range(i, end):
                code[j] = " "
            i = end
            continue
        if char in "\"'":
            raw = i > 0 and text[i - 1] == "r" and (i < 2 or not (text[i - 2].isalnum() or text[i - 2] == "_"))
            quote = text[i:i + 3] if text[i:i + 3] in ('"""', "'''") else char
            start = i + len(quote)
            j = start
            while j < length and not text.startswith(quote, j):
                if text[j] == "\\" and not raw:
                    j += 1
                elif text[j] == "\n" and len(quote) == 1:
                    break
                j += 1
            strings.append((i, text[start:j]))
            for k in range(start, min(j, length)):
                if code[k] != "\n":
                    code[k] = " "
            i = j + len(quote)
            continue
        i += 1
    return "".join(code), strings


def line_of(text, offset):
    return text.count("\n", 0, offset) + 1


class Layer:
    def __init__(self, data):
        try:
            self.name = data["name"]
            path = data["path"].strip("/")
        except (KeyError, AttributeError, TypeError) as error:
            raise ConfigError(f"layer needs name and path: {data!r}") from error
        self.wildcard = path.endswith("/*")
        self.path = path[:-2] if self.wildcard else path
        self.may = set(data.get("may_depend_on", []))
        self.allowed_extends = data.get("allowed_extends")
        self.forbidden = [(re.compile(rule["pattern"]), rule["message"])
                          for rule in data.get("forbidden", [])]

    def instance(self, relative):
        """Return the instance name for a project-relative path, or None."""
        if not relative.startswith(self.path + "/"):
            return None
        rest = relative[len(self.path) + 1:]
        if not self.wildcard:
            return self.name
        if "/" not in rest:
            return None
        return self.name + "/" + rest.split("/", 1)[0]


class Checker:
    def __init__(self, root, rules):
        self.root = root
        self.name = rules.get("architecture", "architecture")
        self.source = rules.get("source", "src").strip("/")
        layers = rules.get("layers")
        if not isinstance(layers, list) or not layers:
            raise ConfigError("rules need a non-empty layers list")
        self.layers = [Layer(item) for item in layers]
        names = {layer.name for layer in self.layers}
        for layer in self.layers:
            unknown = layer.may - names
            if unknown:
                raise ConfigError(f"layer {layer.name} depends on unknown layers: {sorted(unknown)}")
        self.autoload_layer = rules.get("autoload_layer")
        if self.autoload_layer is not None and self.autoload_layer not in names:
            raise ConfigError(f"unknown autoload_layer: {self.autoload_layer}")
        self.violations = []

    def locate(self, relative):
        for layer in self.layers:
            instance = layer.instance(relative)
            if instance is not None:
                return layer, instance
        return None, None

    def report(self, relative, line, message):
        self.violations.append(f"{relative}:{line}: {message}")

    def resolve(self, reference, uids):
        if reference.startswith("uid://"):
            return uids.get(reference)
        if reference.startswith("res://"):
            return posixpath.normpath(reference[len("res://"):]) if reference != "res://" else None
        return None

    def depend(self, relative, line, source, target_relative, label):
        if target_relative is None:
            return
        layer, instance = source
        target_layer, target_instance = self.locate(target_relative)
        if target_layer is None or target_instance == instance:
            return
        if target_layer.name not in layer.may:
            self.report(relative, line, f"{instance} -> {target_instance}: {label}")

    def run(self):
        source_dir = self.root / self.source
        files = sorted(p for p in source_dir.rglob("*") if p.is_file() and p.suffix in SCANNED) \
            if source_dir.is_dir() else []
        uids = {}
        classes = {}
        texts = {}
        for path in files:
            relative = path.relative_to(self.root).as_posix()
            text = path.read_text(encoding="utf-8")
            texts[relative] = text
            if path.suffix == ".gd":
                for match in CLASS_NAME.finditer(split_gdscript(text)[0]):
                    classes[match.group(1)] = relative
            else:
                first = text.split("\n", 1)[0]
                match = RESOURCE_UID.search(first)
                if match and first.startswith(("[gd_scene", "[gd_resource")):
                    uids[match.group(1)] = relative
        for path in source_dir.rglob("*.uid") if source_dir.is_dir() else []:
            uids[path.read_text(encoding="utf-8").strip()] = path.relative_to(self.root).with_suffix("").as_posix()
        autoloads = self.read_autoloads()
        names = dict(classes)
        names.update(autoloads)
        identifier = re.compile(r"(?<![\w.$%])(" + "|".join(map(re.escape, sorted(names, key=len, reverse=True)))
                                + r")(?!\w)") if names else None
        for relative, text in texts.items():
            source = self.locate(relative)
            if source[0] is None:
                self.report(relative, 1, f"outside every layer of {self.name}; move it into a layer directory")
                continue
            if relative.endswith(".gd"):
                self.check_script(relative, text, source, uids, names, identifier, autoloads)
            else:
                for match in RESOURCE_PATH.finditer(text):
                    self.depend(relative, line_of(text, match.start()), source,
                                self.resolve(match.group(1), uids), f'"{match.group(1)}"')
        return len(texts)

    def read_autoloads(self):
        project = self.root / "project.godot"
        autoloads = {}
        if not project.is_file():
            return autoloads
        section = None
        for number, line in enumerate(project.read_text(encoding="utf-8").splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("[") and stripped.endswith("]"):
                section = stripped[1:-1]
                continue
            if section != "autoload":
                continue
            match = AUTOLOAD.match(line)
            if not match:
                continue
            name, reference = match.groups()
            target = self.resolve(reference, {})
            autoloads[name] = target
            if self.autoload_layer is not None:
                layer, _ = self.locate(target)
                if layer is None or layer.name != self.autoload_layer:
                    expected = next(item.path for item in self.layers if item.name == self.autoload_layer)
                    self.report("project.godot", number, f"autoload {name} must live under {expected}/ ({reference})")
        return autoloads

    def check_script(self, relative, text, source, uids, names, identifier, autoloads):
        layer = source[0]
        code, strings = split_gdscript(text)
        for offset, value in strings:
            line = line_of(text, offset)
            if value.startswith(("res://", "uid://")):
                self.depend(relative, line, source, self.resolve(value, uids), f'"{value}"')
            elif value.startswith("/root/"):
                name = value[len("/root/"):].split("/", 1)[0]
                if name in autoloads:
                    self.depend(relative, line, source, autoloads[name], f'autoload {name} ("{value}")')
        if identifier is not None:
            for match in identifier.finditer(code):
                name = match.group(1)
                kind = "autoload" if name in autoloads else "class_name"
                self.depend(relative, line_of(text, match.start()), source, names[name], f"{kind} {name}")
        if layer.allowed_extends is not None:
            for match in EXTENDS.finditer(code):
                base = match.group(1).split(".", 1)[0]
                if base not in layer.allowed_extends and base not in names:
                    allowed = ", ".join(layer.allowed_extends)
                    self.report(relative, line_of(text, match.start()),
                                f"{layer.name} may only extend {allowed} or its own classes: extends {base}")
        for pattern, message in layer.forbidden:
            for match in pattern.finditer(code):
                self.report(relative, line_of(text, match.start()), message)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Check Godot layer dependencies.")
    parser.add_argument("--root", default=".", help="Godot project directory (default: .)")
    parser.add_argument("rules", nargs="?", default="architecture.json", help="rules JSON")
    args = parser.parse_args(argv)
    if sys.version_info < (3, 9):
        print("error: python 3.9+ is required", file=sys.stderr)
        return 2
    root = Path(args.root).resolve()
    rules_path = Path(args.rules)
    if not rules_path.is_absolute():
        rules_path = root / rules_path
    try:
        try:
            rules = json.loads(rules_path.read_text(encoding="utf-8"))
        except FileNotFoundError as error:
            raise ConfigError(f"rules file not found: {rules_path} "
                              "(copy one of architecture/*.json to architecture.json; see README)") from error
        except json.JSONDecodeError as error:
            raise ConfigError(f"invalid rules JSON {rules_path}: {error}") from error
        checker = Checker(root, rules)
        count = checker.run()
    except ConfigError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    for violation in checker.violations:
        print(violation)
    print(f"architecture ({checker.name}): {count} files, {len(checker.violations)} violations")
    return 1 if checker.violations else 0


if __name__ == "__main__":
    sys.exit(main())
