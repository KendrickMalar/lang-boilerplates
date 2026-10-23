"""Git-ignored Rojo fixtures using already-installed Rokit tools; never installs anything."""
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import time
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LEAF = ROOT / "roblox/rojo"
CACHE = ROOT / ".verification/native/roblox"
SEED = CACHE / "seed"
GREETING_SOURCE = """--!strict
local Greeting = {}

function Greeting.format(name: string): string
\treturn `Hello, {name}!`
end

return Greeting
"""
GREETING_SPEC = """--!strict
local Greeting = require("../src/shared/Greeting")

return {
\t["formats a name"] = function()
\t\tassert(Greeting.format("Roblox") == "Hello, Roblox!", "unexpected greeting")
\tend,
}
"""


def tool_bin_dir() -> Path:
    """Link pinned binaries from Rokit storage so a synthetic HOME cannot break shims."""
    pins = tomllib.loads((LEAF / "rokit.toml").read_text())["tools"]
    # Rokit 1.2.0 internal layout: <owner>/<repo>/<version>/<binary>, lowercased.
    # Not a public contract; re-check after upgrading Rokit if this raises.
    storage = Path.home() / ".rokit/tool-storage"
    bin_dir = CACHE / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    for name, spec in pins.items():
        repo, version = spec.split("@")
        owner, project = repo.lower().split("/")
        real = storage / owner / project / version / name
        if not real.is_file():
            raise RuntimeError(f"{real} missing; run approved `rokit install` first")
        link = bin_dir / name
        if link.is_symlink() and link.resolve() == real.resolve():
            continue
        if link.is_symlink() or link.exists():
            raise RuntimeError(f"unknown existing tool link/file preserved: {link}")
        link.symlink_to(real)
    return bin_dir


def roblox_env(root: Path) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith(("ROKIT", "GIT_"))}
    home = root / "home"
    home.mkdir(exist_ok=True)
    env.update(HOME=str(home), PATH=os.pathsep.join([str(tool_bin_dir()), "/usr/bin", "/bin"]))
    return env



def copy_similarity_tool(root: Path, supplied: Path | None = None) -> Path:
    """Copy only an explicitly supplied, pinned existing release; no authentication/download."""
    supplied_value = str(supplied) if supplied is not None else os.environ.get("LUAU_SIMILARITY_BINARY")
    if not supplied_value:
        raise RuntimeError("explicit LUAU_SIMILARITY_BINARY prerequisite required; no automatic download")
    source = Path(supplied_value)
    lock_file = root / "luau-similarity.lock.json"
    lock = json.loads(lock_file.read_text())
    if source.is_symlink() or not source.is_file():
        raise RuntimeError("similarity source must be an existing regular binary")
    if hashlib.sha256(source.read_bytes()).hexdigest() != lock["binary_sha256"]:
        raise RuntimeError("similarity source hash differs from lock")
    directory = root / ".tools/luau-similarity"
    directory.mkdir(parents=True, exist_ok=False)
    binary = directory / "luau-similarity"
    shutil.copy2(source, binary)
    # Lune embeds these declarations; isolate setup from the user's HOME and project config.
    setup = root / ".verification/lune-setup"
    home = root / ".verification/lune-home"
    setup.mkdir(parents=True)
    home.mkdir(parents=True)
    env = roblox_env(root)
    env["HOME"] = str(home)
    result = subprocess.run([str(tool_bin_dir() / "lune"), "setup"], cwd=setup, env=env,
                            text=True, capture_output=True, check=False)
    if result.returncode:
        raise RuntimeError("fixture-local Lune type generation failed")
    types = directory / "lune-types"
    shutil.copytree(home / ".lune/.typedefs/0.10.5", types)
    (types / ".luaurc").write_text(json.dumps({"aliases": {"lune": "."},
                                             "languageMode": "strict", "lintErrors": True}))
    (directory / "installation.json").write_text(json.dumps({
        "schema": 1, "lock_sha256": hashlib.sha256(lock_file.read_bytes()).hexdigest(),
        "binary_sha256": lock["binary_sha256"],
    }))
    return binary


def copy_fixture(name: str, *, similarity: bool = True) -> Path:
    for needed in ["roblox.yml", "globalTypes-1.69.0.d.luau"]:
        if not (SEED / needed).is_file():
            raise RuntimeError(f"seed file {SEED / needed} missing; prepare the approved Git-ignored seed "
                               "(see roblox/README.md, maintenance prerequisites)")
    CACHE.mkdir(parents=True, exist_ok=True)
    root = Path(tempfile.mkdtemp(prefix=f"{name}-", dir=CACHE)) / "project"
    shutil.copytree(LEAF, root)
    (root / "src/shared/Greeting.luau").write_text(GREETING_SOURCE)
    (root / "tests/Greeting.spec.luau").write_text(GREETING_SPEC)
    shutil.copy2(SEED / "roblox.yml", root / "roblox.yml")
    (root / ".luau-lsp-cache").mkdir()
    shutil.copy2(SEED / "globalTypes-1.69.0.d.luau", root / ".luau-lsp-cache/globalTypes-1.69.0.d.luau")
    if similarity:
        copy_similarity_tool(root)
    return root


def run_check(root: Path, stage: str, env: dict[str, str] | None = None):
    env = env if env is not None else roblox_env(root)
    # Run from outside the fixture: check.sh must locate its own root.
    result = subprocess.run(["sh", str(root / "scripts/check.sh"), stage], cwd=CACHE, env=env,
                            text=True, capture_output=True, check=False)
    logs = CACHE / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    stem = f"{root.parent.name}-{stage}-{time.time_ns()}"
    (logs / f"{stem}.log").write_text(f"exit={result.returncode}\n{result.stdout}\n{result.stderr}")
    (logs / f"{stem}.json").write_text(json.dumps({"fixture": str(root), "stage": stage,
                                                   "exit": result.returncode}, indent=2))
    return result
