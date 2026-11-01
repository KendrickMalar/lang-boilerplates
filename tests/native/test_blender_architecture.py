"""Real fixed-tool acceptance for the Blender architecture options.

Each option's shipped ruff configs are copied next to the leaf pyproject.toml, then
fixtures that keep the dependency direction must pass and fixtures that break it must
fail with the expected rule. Existing ruff 0.17.0 / Blender 5.2.2 are required on PATH;
nothing is installed. Fixtures and logs remain under .verification/.
"""
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LEAF = ROOT / "blender/assets"
CACHE = ROOT / ".verification/native/blender-architecture"
LINT_DIRS = ["models", "parts", "geometry", "tests", "scripts"]

PARTS_OK = 'import bpy\n\n\ndef add_box(size: float) -> None:\n    bpy.ops.mesh.primitive_cube_add(size=size)\n'
MODEL_OK = 'from parts import shapes\n\n\ndef build() -> None:\n    shapes.add_box(1.0)\n'
GEOMETRY_OK = ('def grid(count: int) -> list[tuple[float, float, float]]:\n'
               '    return [(float(i), 0.0, 0.0) for i in range(count)]\n')
PARTS_ADAPTER_OK = ('import bpy\n\nfrom geometry import points\n\n\n'
                    'def add_points(count: int) -> None:\n'
                    '    mesh = bpy.data.meshes.new("points")\n'
                    '    mesh.from_pydata(points.grid(count), [], [])\n')
MODEL_ADAPTER_OK = 'from parts import mesh\n\n\ndef build() -> None:\n    mesh.add_points(3)\n'

# (file, source, rule) that must be rejected under both options.
SHARED_VIOLATIONS = [
    ("models/bad.py", 'import models.box\n\n\ndef build() -> None:\n    models.box.build()\n', "TID251"),
    ("models/bad.py", 'from models import box\n\n\ndef build() -> None:\n    box.build()\n', "TID251"),
    ("models/bad.py", 'from models.box import build as other\n\n\ndef build() -> None:\n    other()\n',
     "TID251"),
    ("models/bad.py", 'from . import box\n\n\ndef build() -> None:\n    box.build()\n', "TID252"),
    ("models/bad.py", 'from .box import build as other\n\n\ndef build() -> None:\n    other()\n',
     "TID252"),
    ("parts/bad.py", 'from models import box\n\n\ndef add() -> None:\n    box.build()\n', "TID251"),
    ("parts/bad.py", 'import models.box\n\n\ndef add() -> None:\n    models.box.build()\n', "TID251"),
]
GEOMETRY_VIOLATIONS = [
    ("geometry/bad.py", 'import bpy\n\n\ndef f() -> object:\n    return bpy.data\n', "TID251"),
    ("geometry/bad.py", 'from bpy import data\n\n\ndef f() -> object:\n    return data\n', "TID251"),
    ("geometry/bad.py", 'import bpy.types\n\n\ndef f() -> object:\n    return bpy.types.Mesh\n', "TID251"),
    ("geometry/bad.py", 'from bpy.types import Mesh\n\n\ndef f() -> object:\n    return Mesh\n', "TID251"),
    ("geometry/bad.py", 'import bmesh\n\n\ndef f() -> object:\n    return bmesh.new()\n', "TID251"),
    ("geometry/bad.py", 'from mathutils import Vector\n\n\ndef f() -> object:\n    return Vector()\n',
     "TID251"),
    ("geometry/bad.py", 'from parts import mesh\n\n\ndef f() -> object:\n    return mesh\n', "TID251"),
    ("geometry/bad.py", 'from models import box\n\n\ndef f() -> object:\n    return box\n', "TID251"),
]


def fixture(prefix):
    CACHE.mkdir(parents=True, exist_ok=True)
    root = Path(tempfile.mkdtemp(prefix=prefix + "-", dir=CACHE))
    (root / "home").mkdir()
    return root


def run(command, root, cwd=None):
    environment = os.environ.copy()
    environment.update(HOME=str(root / "home"))
    result = subprocess.run(command, cwd=cwd or root, env=environment, text=True,
                            capture_output=True, timeout=300, check=False)
    logs = root / "logs"
    logs.mkdir(exist_ok=True)
    path = logs / f"{len(list(logs.iterdir())):03d}.log"
    path.write_text(f"command={command!r}\nexit={result.returncode}\n{result.stdout}\n{result.stderr}")
    return result


def install(option, files):
    """Copy the leaf, then the option's configs to the leaf root, like README says."""
    root = fixture(option)
    project = root / "project"
    shutil.copytree(LEAF, project, ignore=shutil.ignore_patterns("architecture", "node_modules"))
    shutil.copytree(LEAF / "architecture" / option, project, dirs_exist_ok=True)
    for name, source in files.items():
        path = project / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source)
    return root, project


class BlenderArchitectureRuffTests(unittest.TestCase):
    def setUp(self):
        self.ruff = shutil.which("ruff")
        self.assertIsNotNone(self.ruff, "existing ruff 0.17.0 required; do not install")
        version = subprocess.run([self.ruff, "--version"], text=True, capture_output=True, check=False)
        self.assertEqual(version.stdout.strip(), "ruff 0.17.0", "put ruff 0.17.0 first on PATH")

    def lint(self, root, project):
        targets = [name for name in LINT_DIRS if (project / name).is_dir()]
        command = [self.ruff, "check", "--no-cache", "--output-format", "concise", *targets]
        result = run(command, root, project)
        formatted = run([self.ruff, "format", "--check", "--no-cache", *targets], root, project)
        return result, formatted

    def assert_accepts(self, option, files):
        root, project = install(option, files)
        result, formatted = self.lint(root, project)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(formatted.returncode, 0, formatted.stdout + formatted.stderr)

    def assert_rejects(self, option, files, bad, rule):
        root, project = install(option, files)
        result, _ = self.lint(root, project)
        output = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0, output)
        self.assertIn(f"{bad}:1:", output)
        self.assertIn(rule, output)
        # The only diagnostics are the architecture rule, not unrelated noise.
        for line in output.splitlines():
            if line.startswith(("models/", "parts/", "geometry/")):
                self.assertIn(rule, line)

    def test_flat_accepts_models_using_parts(self):
        self.assert_accepts("flat", {"parts/shapes.py": PARTS_OK, "models/box.py": MODEL_OK})

    def test_flat_rejects_model_to_model_and_parts_to_models(self):
        for bad, source, rule in SHARED_VIOLATIONS:
            with self.subTest(bad=bad, source=source.splitlines()[0]):
                files = {"parts/shapes.py": PARTS_OK, "models/box.py": MODEL_OK, bad: source}
                self.assert_rejects("flat", files, bad, rule)

    def test_geometry_accepts_pure_geometry_adapter_and_models(self):
        self.assert_accepts("geometry", {"geometry/points.py": GEOMETRY_OK,
                                         "parts/mesh.py": PARTS_ADAPTER_OK,
                                         "models/box.py": MODEL_ADAPTER_OK})

    def test_geometry_rejects_blender_and_upward_imports(self):
        base = {"geometry/points.py": GEOMETRY_OK, "parts/mesh.py": PARTS_ADAPTER_OK,
                "models/box.py": MODEL_ADAPTER_OK}
        for bad, source, rule in SHARED_VIOLATIONS + GEOMETRY_VIOLATIONS:
            with self.subTest(bad=bad, source=source.splitlines()[0]):
                self.assert_rejects("geometry", {**base, bad: source}, bad, rule)

    def test_option_templates_do_not_break_whole_leaf_lint(self):
        # architecture/*/ruff.toml extend paths only resolve after copying; ruff . must skip them.
        root = fixture("pristine")
        project = root / "project"
        shutil.copytree(LEAF, project, ignore=shutil.ignore_patterns("node_modules"))
        for command in [[self.ruff, "check", "--no-cache", "."],
                        [self.ruff, "format", "--check", "--no-cache", "."]]:
            result = run(command, root, project)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_dynamic_import_is_a_documented_gap(self):
        # README states ruff cannot see importlib.import_module("bpy"); pin that fact.
        source = 'import importlib\n\n\ndef f() -> object:\n    return importlib.import_module("bpy")\n'
        self.assert_accepts("geometry", {"geometry/points.py": GEOMETRY_OK, "geometry/dyn.py": source})
        self.assertIn('importlib.import_module("bpy")', (LEAF / "README.md").read_text())


class BlenderArchitectureBuildTests(unittest.TestCase):
    def test_models_can_import_parts_and_geometry_in_headless_blender(self):
        blender = shutil.which("blender")
        self.assertIsNotNone(blender, "existing Blender 5.2.2 required; do not install")
        root, project = install("geometry", {
            "geometry/points.py": GEOMETRY_OK,
            "parts/shapes.py": ('import bpy\n\nfrom geometry import points\n\n\n'
                                'def add_boxes(count: int) -> None:\n'
                                '    for location in points.grid(count):\n'
                                '        bpy.ops.mesh.primitive_cube_add(size=0.5, location=location)\n'),
            "models/row.py": ('from parts import shapes\n\n\n'
                              'def build() -> None:\n    shapes.add_boxes(2)\n'),
        })
        version = run([blender, "--version"], root)
        self.assertTrue(version.stdout.startswith("Blender 5.2.2"), version.stdout)
        out = root / "out"
        result = run([blender, "-b", "--factory-startup", "--python-exit-code", "1", "--python",
                      str(project / "scripts/build.py"), "--", "--out", str(out)], root)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("BUILT row.glb (24 triangles)", result.stdout)
        self.assertTrue((out / "row.glb").is_file())


if __name__ == "__main__":
    unittest.main()
