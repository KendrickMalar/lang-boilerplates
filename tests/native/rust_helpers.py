"""Git-ignored, isolated Cargo fixtures; never product source in the leaf."""
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LEAF = ROOT / "rust/tauri"
CACHE = ROOT / ".verification/native/rust"
LIB_SOURCE = """pub fn add(left: u32, right: u32) -> u32 {
    left + right
}

#[cfg(test)]
mod tests {
    #[test]
    fn adds() {
        assert_eq!(super::add(2, 3), 5);
    }
}
"""


def rust_env(cwd: Path | None = None):
    env = os.environ.copy()
    home = (cwd if cwd else CACHE).resolve() / "home"
    home.mkdir(parents=True, exist_ok=True)
    env.update(HOME=str(home), CFFIXED_USER_HOME=str(home), RUSTUP_AUTO_INSTALL="0",
               RUSTUP_HOME=str(CACHE / "rustup"), CARGO_HOME=str(CACHE / "cargo"),
               CARGO_TARGET_DIR=str(CACHE / "targets" / cwd.name if cwd else CACHE / "target"),
               CARGO_NET_OFFLINE="true")
    # Existing rustup proxy only; check scripts select installed tools without download.
    rustup = shutil.which("rustup")
    if rustup is None:
        raise RuntimeError("rustup is missing; no automatic installation")
    proxy = Path(rustup).parent
    env["PATH"] = str(proxy) + os.pathsep + env["PATH"]
    return env


def run_rust(command: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    env = rust_env(cwd)
    result = subprocess.run(command, cwd=cwd, env=env, text=True,
                            capture_output=True, check=False)
    logs = CACHE / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    stem = f"{cwd.name}-{time.time_ns()}"
    (logs / f"{stem}.log").write_text(
        f"cwd={cwd}\ncommand={command!r}\nexit={result.returncode}\n{result.stdout}\n{result.stderr}")
    (logs / f"{stem}.json").write_text(json.dumps({
        "cwd": str(cwd), "target": env["CARGO_TARGET_DIR"],
        "environment": {key: env[key] for key in ("HOME", "CFFIXED_USER_HOME", "CARGO_HOME",
                         "RUSTUP_HOME", "CARGO_TARGET_DIR", "RUSTUP_AUTO_INSTALL", "CARGO_NET_OFFLINE")},
        "command": command, "exit": result.returncode,
        "files_sha256": _rust_input_hashes(cwd),
        "test_results": re.findall(r"test result:.*", result.stdout),
        "log": str(logs / f"{stem}.log"),
    }, indent=2))
    return result


def _rust_input_hashes(cwd: Path) -> dict[str, str]:
    # Capture arbitrary nested source/config inputs, pruning outputs before traversal.
    paths = [cwd / name for name in ("rust-toolchain.toml", "rustfmt.toml", ".editorconfig", ".gitignore")]
    # Only Cargo/Tauri output paths are excluded; names inside sources are inputs.
    generated = {cwd / "src-tauri" / "target", cwd / "src-tauri" / "gen"}
    for name in ("src-tauri", ".cargo", "scripts", ".githooks", "dist"):
        for directory, children, files in os.walk(cwd / name):
            children[:] = [child for child in children
                           if child != ".git" and Path(directory) / child not in generated]
            paths.extend(Path(directory) / file for file in files)
    return {str(path.relative_to(cwd)): _sha256(path) for path in sorted(paths) if path.is_file()}


def copy_rust_fixture(*, frontend: bool = True) -> Path:
    CACHE.mkdir(parents=True, exist_ok=True)
    fixture = Path(tempfile.mkdtemp(prefix="fixture-", dir=CACHE))
    shutil.copytree(LEAF, fixture, dirs_exist_ok=True)
    source = fixture / "src-tauri/src"
    source.mkdir()
    (source / "lib.rs").write_text(LIB_SOURCE)
    (source / "main.rs").write_text("fn main() {}\n")
    if frontend:
        (fixture / "dist").mkdir()
        (fixture / "dist/index.html").write_text("<!doctype html><title>Fixture</title>\n")
    approved = CACHE / "approved-resolution"
    if not (approved / "approval.json").is_file():
        raise RuntimeError("dependency approval absent; stop and consult supervisor")
    shutil.copyfile(approved / "Cargo.lock", fixture / "src-tauri/Cargo.lock")
    result = run_rust(["rustup", "run", "1.92.0", "cargo", "metadata", "--offline", "--locked",
                       "--format-version", "1", "--manifest-path", "src-tauri/Cargo.toml"], fixture)
    if result.returncode:
        raise RuntimeError(f"metadata failed; stop and consult supervisor:\n{result.stdout}\n{result.stderr}")
    metadata = json.loads(result.stdout)
    (fixture / "metadata.json").write_text(json.dumps(metadata, indent=2))
    undeclared = validate_rust_dependencies(metadata, fixture / "src-tauri/Cargo.lock", approved)
    if undeclared:
        verify_conditional_msrv(fixture, undeclared)
    return fixture


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _package_records(metadata: dict) -> list[dict]:
    return sorted([{key: package.get(key) for key in ("name", "version", "source", "rust_version")}
                   for package in metadata["packages"]],
                  key=lambda package: (package["name"], package["version"], str(package["source"])))


def validate_rust_dependencies(metadata: dict, lock: Path, approved: Path) -> list[dict]:
    """Only the approved fixed resolution is eligible; missing MSRV is not a pass."""
    for package in metadata["packages"]:
        version = package.get("rust_version")
        numbers = tuple(map(int, version.split("."))) if version else ()
        if version and (numbers + (0,) * (3 - len(numbers))) > (1, 92, 0):
            raise RuntimeError(f"MSRV mismatch: {package['name']} requires {version}; consult supervisor")
    try:
        approval = json.loads((approved / "approval.json").read_text())
        lock_hash = _sha256(lock)
        if lock_hash != approval["lock_sha256"] or lock_hash != _sha256(approved / "Cargo.lock"):
            raise RuntimeError("unapproved lock; consult supervisor")
        packages = _package_records(metadata)
        if packages != approval["packages"]:
            raise RuntimeError("unknown dependency name/version/source/MSRV; consult supervisor")
        undeclared = [package for package in packages if package["rust_version"] is None]
        if undeclared != approval["undeclared_msrv"]:
            raise RuntimeError("unknown undeclared MSRV set; consult supervisor")
        if undeclared:
            if sys.platform != "darwin" or approval["platform"] != "darwin" or platform.machine() != approval["arch"]:
                raise RuntimeError("MSRV evidence does not cover this platform; consult supervisor")
            for stage in ("build", "test"):
                entry = approval["evidence"][stage]
                log = approved / entry["file"]
                proof = json.loads(log.read_text())
                if (_sha256(log) != entry["sha256"] or proof["exit"] != 0
                        or proof["lock_sha256"] != lock_hash
                        or proof["command"] != ["sh", "scripts/check.sh", stage]
                        or proof["platform"] != approval["platform"] or proof["arch"] != approval["arch"]
                        or proof["rustc"] != approval["rustc"]
                        or proof["source_sha256"] != approval["source_sha256"]
                        or f"stage: {stage}" not in proof["stdout"]
                        or (stage == "test" and not re.search(r"test result: ok\. [1-9][0-9]* passed;", proof["stdout"]))):
                    raise RuntimeError("invalid conditional MSRV evidence; consult supervisor")
            tool = approval["rustc"]
            if not tool["version"].startswith("rustc 1.92.0 ") or _sha256(Path(tool["path"])) != tool["sha256"]:
                raise RuntimeError("conditional MSRV tool evidence changed; consult supervisor")
        return undeclared
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise RuntimeError(f"dependency approval/evidence unavailable; consult supervisor: {error}") from error


def verify_conditional_msrv(fixture: Path, undeclared: list[dict]) -> None:
    """Require actual build and nonempty passing tests on this fixture's own target."""
    if sys.platform != "darwin":
        raise RuntimeError("conditional MSRV only approved on macOS; consult supervisor")
    tool = next((CACHE / "rustup/toolchains").glob("1.92.0-*/bin/rustc"))
    version = run_rust([str(tool), "--version"], fixture)
    if version.returncode or not version.stdout.startswith("rustc 1.92.0 "):
        raise RuntimeError("conditional MSRV requires real Rust1.92.0; consult supervisor")
    evidence = {"lock_sha256": _sha256(fixture / "src-tauri/Cargo.lock"),
                "undeclared_msrv": undeclared, "platform": sys.platform, "arch": platform.machine(),
                "target": rust_env(fixture)["CARGO_TARGET_DIR"],
                "rustc": {"path": str(tool), "version": version.stdout.strip(), "sha256": _sha256(tool)},
                "source_sha256": {str(path.relative_to(fixture)): _sha256(path)
                                  for path in sorted((fixture / "src-tauri/src").glob("*.rs"))},
                "commands": []}
    for stage in ("build", "test"):
        command = ["sh", "scripts/check.sh", stage]
        result = run_rust(command, fixture)
        evidence["commands"].append({"command": command, "exit": result.returncode,
                                     "stdout": result.stdout, "stderr": result.stderr})
        receipt = json.dumps(evidence, indent=2)
        (fixture / f"dependency-evidence-{time.time_ns()}.json").write_text(receipt)
        (fixture / "dependency-evidence.json").write_text(receipt)
        if result.returncode or (stage == "test" and not re.search(r"test result: ok\. [1-9][0-9]* passed;", result.stdout)):
            raise RuntimeError(f"conditional MSRV {stage} evidence failed; consult supervisor")


def restore_rust_baseline(fixture: Path, baseline: dict[Path, bytes]) -> None:
    """Rewrite only this class's owned files, without restoring old mtimes."""
    for path, contents in baseline.items():
        if not path.is_relative_to(fixture):
            raise RuntimeError("baseline outside owned fixture")
        path.write_bytes(contents)
    if any(path.read_bytes() != contents for path, contents in baseline.items()):
        raise RuntimeError("fixture baseline restoration failed")


TAURI_LIB_SOURCE = '''mod commands {
    #[tauri::command]
    pub fn allowed() -> &'static str {
        "allowed result"
    }

    #[tauri::command]
    pub fn denied() -> &'static str {
        "denied result"
    }
}

pub fn run() -> Result<(), Box<dyn std::error::Error>> {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![
            commands::allowed,
            commands::denied
        ])
        .run(tauri::generate_context!())?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use tauri::test::{INVOKE_KEY, get_ipc_response, mock_builder};

    #[test]
    fn allowed_and_denied_ipc() -> Result<(), Box<dyn std::error::Error>> {
        let app = mock_builder()
            .invoke_handler(tauri::generate_handler![
                super::commands::allowed,
                super::commands::denied
            ])
            .build(tauri::generate_context!())?;
        let main = tauri::WebviewWindowBuilder::new(&app, "main", Default::default()).build()?;
        let other = tauri::WebviewWindowBuilder::new(&app, "other", Default::default()).build()?;
        let invoke =
            |window: &tauri::WebviewWindow<tauri::test::MockRuntime>, cmd: &str, url: &str| {
                Ok::<_, Box<dyn std::error::Error>>(get_ipc_response(
                    window,
                    tauri::webview::InvokeRequest {
                        cmd: cmd.into(),
                        callback: tauri::ipc::CallbackFn(0),
                        error: tauri::ipc::CallbackFn(1),
                        url: url.parse()?,
                        body: tauri::ipc::InvokeBody::default(),
                        headers: Default::default(),
                        invoke_key: INVOKE_KEY.into(),
                    },
                ))
            };
        let allowed = invoke(&main, "allowed", "tauri://localhost")?;
        assert!(allowed.is_ok(), "allowed app command denied: {allowed:?}");
        if let Ok(body) = allowed {
            assert_eq!(body.deserialize::<String>()?, "allowed result");
        }
        let denied = invoke(&main, "denied", "tauri://localhost")?;
        assert!(denied.is_err(), "unregistered command bypassed ACL");
        assert!(format!("{denied:?}").contains("not allowed"));
        assert!(invoke(&other, "allowed", "tauri://localhost")?.is_err());
        assert!(invoke(&main, "allowed", "https://remote.invalid")?.is_err());
        assert!(invoke(&main, "plugin:window|title", "tauri://localhost")?.is_ok());
        let denied_core = invoke(&main, "plugin:window|close", "tauri://localhost")?;
        assert!(denied_core.is_err());
        assert!(format!("{denied_core:?}").contains("not allowed"));
        Ok(())
    }
}
'''


def configure_tauri_fixture(fixture: Path) -> None:
    """Fixture-only commands/features; no product implementation is distributed."""
    # Tauri generate_context requires a PNG icon; generated only in the ignored fixture.
    import struct
    import zlib
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    icons = fixture / "src-tauri/icons"
    icons.mkdir(exist_ok=True)
    (icons / "icon.png").write_bytes(b"\x89PNG\r\n\x1a\n" +
        chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0)) +
        chunk(b"IDAT", zlib.compress(b"\x00\x00\x00\x00\xff")) + chunk(b"IEND", b""))
    manifest = fixture / "src-tauri/Cargo.toml"
    manifest.write_text(manifest.read_text().replace(
        'tauri = { version = "=2.12.2" }',
        'tauri = { version = "=2.12.2", features = ["test", "custom-protocol"] }'))
    build = fixture / "src-tauri/build.rs"
    build.write_text(build.read_text().replace('.commands(&[])', '.commands(&["allowed", "denied"])'))
    capability = fixture / "src-tauri/capabilities/main.json"
    value = json.loads(capability.read_text())
    value["permissions"].append("allow-allowed")
    capability.write_text(json.dumps(value))
    (fixture / "src-tauri/src/lib.rs").write_text(TAURI_LIB_SOURCE)
    (fixture / "src-tauri/src/main.rs").write_text(
        'fn main() -> Result<(), Box<dyn std::error::Error>> {\n    native_app_lib::run()\n}\n')
    result = run_rust(["rustup", "run", "1.92.0", "cargo", "metadata", "--offline", "--locked",
                       "--format-version", "1", "--manifest-path", "src-tauri/Cargo.toml"], fixture)
    if result.returncode:
        raise RuntimeError("native metadata failed; consult supervisor: " + result.stderr)
    undeclared = validate_rust_dependencies(json.loads(result.stdout), fixture / "src-tauri/Cargo.lock",
                                           CACHE / "approved-resolution")
    if undeclared:
        verify_conditional_msrv(fixture, undeclared)
