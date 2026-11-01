"""Build every models/<name>.py into <out>/<name>.glb inside headless Blender.

Usage: blender -b --factory-startup --python-exit-code 1 --python scripts/build.py -- --out DIR
"""

import argparse
import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import bpy

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MAX_TRIANGLES = 3000


def parse_args() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser(prog="build.py")
    parser.add_argument("--out", type=Path, required=True)
    return parser.parse_args(argv)


def load_model(path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(f"models.{path.stem}", path)
    if spec is None or spec.loader is None:
        raise ValueError(f"{path.name}: cannot load module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not callable(getattr(module, "build", None)):
        raise ValueError(f"{path.name}: define build() -> None")
    return module


def triangle_count() -> int:
    depsgraph = bpy.context.evaluated_depsgraph_get()
    total = 0
    for obj in bpy.context.scene.objects:
        if obj.type != "MESH":
            continue
        evaluated = obj.evaluated_get(depsgraph)
        mesh = evaluated.to_mesh()
        mesh.calc_loop_triangles()
        total += len(mesh.loop_triangles)
        evaluated.to_mesh_clear()
    return total


def build_one(path: Path, out: Path) -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    module = load_model(path)
    module.build()
    limit = getattr(module, "MAX_TRIANGLES", DEFAULT_MAX_TRIANGLES)
    count = triangle_count()
    if count == 0:
        raise ValueError(f"{path.name}: build() created no mesh triangles")
    if count > limit:
        raise ValueError(f"{path.name}: {count} triangles exceeds MAX_TRIANGLES={limit}")
    target = out / f"{path.stem}.glb"
    bpy.ops.export_scene.gltf(filepath=str(target), export_format="GLB")
    print(f"BUILT {target.name} ({count} triangles)")


def main() -> int:
    args = parse_args()
    # Lets models/*.py import parts/ and geometry/ (README「アーキテクチャ」).
    sys.path.insert(0, str(ROOT))
    models = sorted(p for p in (ROOT / "models").glob("*.py") if not p.name.startswith("_"))
    if not models:
        print("FAIL no models/*.py found")
        return 1
    args.out.mkdir(parents=True, exist_ok=True)
    failed = 0
    for path in models:
        try:
            build_one(path, args.out)
        except Exception as error:  # report every model, then fail
            failed += 1
            print(f"FAIL {path.name}: {error}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
