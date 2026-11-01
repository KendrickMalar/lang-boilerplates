"""Git-ignored, isolated toolchain and fixtures for the Rust server leaves."""
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / ".verification/native/rust-game"
LEAVES = ("game", "web-game", "web")


def game_env(cwd: Path, *, online: bool = False) -> dict[str, str]:
    env = os.environ.copy()
    home = cwd.resolve() / "home"
    home.mkdir(parents=True, exist_ok=True)
    env.update(HOME=str(home), CFFIXED_USER_HOME=str(home), RUSTUP_AUTO_INSTALL="0",
               RUSTUP_HOME=str(CACHE / "rustup"), CARGO_HOME=str(CACHE / "cargo"),
               CARGO_TARGET_DIR=str(CACHE / "targets" / cwd.name),
               CARGO_NET_OFFLINE="true")
    if online:
        del env["CARGO_NET_OFFLINE"]
    # Existing rustup proxy only; the toolchain itself lives under CACHE.
    rustup = shutil.which("rustup")
    if rustup is None:
        raise RuntimeError("rustup is missing; no automatic installation")
    env["PATH"] = os.pathsep.join([str(CACHE / "tools/bin"), str(Path(rustup).parent), env["PATH"]])
    return env


def copy_leaf(leaf: str, prefix: str) -> Path:
    if leaf not in LEAVES:
        raise ValueError(f"unknown leaf: {leaf}")
    (CACHE / "fixtures").mkdir(parents=True, exist_ok=True)
    fixture = Path(tempfile.mkdtemp(prefix=f"{prefix}-", dir=CACHE / "fixtures")) / "project"
    shutil.copytree(ROOT / "rust" / leaf, fixture)
    return fixture


def write_fake_crate(root: Path, name: str, lib: str) -> str:
    """Create an unpublished stand-in crate under vendor/ and return its dependency line.

    The workspace must exclude it: add `exclude = ["vendor"]` to `[workspace]`.
    """
    crate = root / "vendor" / name
    (crate / "src").mkdir(parents=True, exist_ok=True)
    (crate / "Cargo.toml").write_text(
        f'[package]\nname = "{name}"\nversion = "0.1.0"\nedition = "2024"\npublish = false\n')
    (crate / "src/lib.rs").write_text(lib)
    return f'{name} = {{ path = "../../vendor/{name}" }}'


def run_game(command: list[str], cwd: Path, *, online: bool = False) -> subprocess.CompletedProcess[str]:
    env = game_env(cwd, online=online)
    result = subprocess.run(command, cwd=cwd, env=env, text=True,
                            capture_output=True, check=False)
    logs = CACHE / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    stem = f"{cwd.name}-{time.time_ns()}"
    (logs / f"{stem}.log").write_text(
        f"cwd={cwd}\ncommand={command!r}\nexit={result.returncode}\n{result.stdout}\n{result.stderr}")
    keys = ("HOME", "CFFIXED_USER_HOME", "CARGO_HOME", "RUSTUP_HOME", "CARGO_TARGET_DIR",
            "RUSTUP_AUTO_INSTALL", "CARGO_NET_OFFLINE")
    (logs / f"{stem}.json").write_text(json.dumps({
        "cwd": str(cwd), "target": env["CARGO_TARGET_DIR"],
        "environment": {key: env.get(key) for key in keys},
        "command": command, "exit": result.returncode,
        "test_results": re.findall(r"test result:.*", result.stdout),
        "log": str(logs / f"{stem}.log"),
    }, indent=2))
    return result
