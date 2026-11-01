"""Real-tool gates for the architecture choices of the Rust server leaves.

Each fixture copies one leaf, selects one choice (architecture/<choice>/* -> architecture/),
and builds the crate graph from the distributed layers.conf and deny.toml: every allowed edge
is present, so a passing check proves the files accept their own design. Violations add one
edge (or a stand-in crate) and must fail the deps stage. Offline: external crates are
path-only stand-ins under vendor/.
"""
import shutil
import subprocess
import tomllib
import unittest
from pathlib import Path

from tests.native.rust_game_helpers import copy_leaf, run_game
from tests.native.test_rust_game import CLEAN
from tests.native.test_static_rust_game import CHOICES, layers

STAND_IN = "pub fn touch() {}\n"


def ident(crate: str) -> str:
    return crate.replace("-", "_")


def write_vendor(root: Path, name: str, deps: tuple[str, ...] = ()) -> None:
    crate = root / "vendor" / name
    (crate / "src").mkdir(parents=True, exist_ok=True)
    lines = "".join(f'{dep} = {{ path = "../{dep}" }}\n' for dep in deps)
    (crate / "Cargo.toml").write_text(
        f'[package]\nname = "{name}"\nversion = "0.1.0"\nedition = "2024"\npublish = false\n'
        f'\n[dependencies]\n{lines}')
    uses = "".join(f"pub use {ident(dep)};\n" for dep in sorted(deps, key=ident))
    (crate / "src/lib.rs").write_text(uses or STAND_IN)


def write_member(root: Path, name: str, internal: set[str], external: set[str]) -> None:
    crate = root / "crates" / name
    (crate / "src").mkdir(parents=True, exist_ok=True)
    lines = "".join(f'{dep} = {{ path = "../{dep}" }}\n' for dep in sorted(internal))
    lines += "".join(f'{dep} = {{ path = "../../vendor/{dep}" }}\n' for dep in sorted(external))
    (crate / "Cargo.toml").write_text(
        f'[package]\nname = "{name}"\nversion = "0.1.0"\n'
        'edition.workspace = true\nrust-version.workspace = true\npublish.workspace = true\n'
        f'\n[dependencies]\n{lines}\n[lints]\nworkspace = true\n')
    reexports = "".join(f"pub use {ident(dep)};\n"
                        for dep in sorted(internal | external, key=ident))
    body = CLEAN.split("\n", 1)[1]  # drop the crate doc line
    (crate / "src/lib.rs").write_text(
        f"//! Layer {name}.\n" + (f"\n{reexports}" if reexports else "") + body)


class ArchitectureFixture(unittest.TestCase):
    def build(self, leaf: str, choice: str, *, add: dict[str, set[str]] | None = None,
              vendor: dict[str, tuple[str, ...]] | None = None, select: bool = True,
              externals: bool = True, drop: dict[str, set[str]] | None = None) -> Path:
        """add: extra dependencies per member (a new key adds a member); vendor: stand-ins;
        drop: allowed edges to remove, so that an upward edge does not make a Cargo cycle."""
        root = copy_leaf(leaf, f"arch-{choice}")
        chosen = root / "architecture" / choice
        uses, _ = layers(chosen / "layers.conf")
        wrappers = {entry["crate"]: entry["wrappers"]
                    for entry in tomllib.loads((chosen / "deny.toml").read_text())["bans"]["deny"]}
        if select:
            for file in chosen.iterdir():
                shutil.copy(file, root / "architecture" / file.name)
        graph = {crate: set(deps) for crate, deps in uses.items()}
        for crate, allowed in (wrappers.items() if externals else ()):
            for member in allowed:
                graph[member].add(crate)
        for crate, deps in (add or {}).items():
            graph.setdefault(crate, set()).update(deps)
        for crate, deps in (drop or {}).items():
            graph[crate] -= deps
        stand_ins = dict(vendor or {})
        for deps in graph.values():
            for dep in deps - set(graph):
                stand_ins.setdefault(dep, ())
        for name, deps in stand_ins.items():
            write_vendor(root, name, deps)
        for crate, deps in graph.items():
            write_member(root, crate, deps & set(graph), deps - set(graph))
        manifest = root / "Cargo.toml"
        manifest.write_text(manifest.read_text().replace(
            'members = ["crates/*"]\n', 'members = ["crates/*"]\nexclude = ["vendor"]\n'))
        locked = run_game(["cargo", "generate-lockfile", "--offline"], root)
        self.assertEqual(locked.returncode, 0, locked.stderr)
        return root

    def deps(self, root: Path) -> subprocess.CompletedProcess[str]:
        return run_game(["sh", "scripts/check.sh", "deps"], root)

    def assert_rejected(self, leaf: str, choice: str, needle: str, **build) -> None:
        result = self.deps(self.build(leaf, choice, **build))
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(needle, result.stderr)
        self.assertNotIn("architecture: ok", result.stdout)


BANNED = "is explicitly banned"


class ArchitectureKeepTests(ArchitectureFixture):
    def test_every_choice_passes_commit(self):
        for leaf, choices in CHOICES.items():
            for choice in choices:
                with self.subTest(leaf=leaf, choice=choice):
                    root = self.build(leaf, choice)
                    result = run_game(["sh", "scripts/check.sh", "commit"], root)
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    self.assertIn("architecture: ok (architecture/layers.conf, "
                                  "architecture/deny.toml)", result.stdout)

    def test_before_external_crates_passes_with_unused_wrapper_warnings(self):
        # A new project selects its architecture before adding axum or sqlx.
        result = self.deps(self.build("web", "hexagonal", externals=False))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("warning[unused-wrapper]", result.stderr)
        self.assertIn("architecture: ok", result.stdout)

    def test_without_selection_is_skipped(self):
        result = self.deps(self.build("web", "hexagonal", select=False))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("architecture: skipped (no architecture/layers.conf)", result.stdout)


class ArchitectureScriptTests(ArchitectureFixture):
    def test_unlisted_member_rejected(self):
        self.assert_rejected("web", "two-crate",
                             "workspace crate extra has no `extra uses ...` line",
                             add={"extra": set()})

    def test_missing_deny_fragment_rejected(self):
        root = self.build("web", "two-crate")
        (root / "architecture/deny.toml").unlink()
        result = self.deps(root)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("missing architecture/deny.toml", result.stderr)

    def test_unknown_key_rejected(self):
        root = self.build("web", "two-crate")
        with (root / "architecture/layers.conf").open("a") as conf:
            conf.write("core allows tokio\n")
        result = self.deps(root)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unknown key `allows` (uses|never)", result.stderr)

    def test_dev_dependency_is_not_checked(self):
        root = self.build("game", "minimal")
        manifest = root / "crates/rules/Cargo.toml"
        write_vendor(root, "tokio")
        manifest.write_text(manifest.read_text().replace(
            "\n[lints]", '\n[dev-dependencies]\ntokio = { path = "../../vendor/tokio" }\n\n[lints]'))
        tests = root / "crates/rules/tests"
        tests.mkdir()
        (tests / "uses_tokio.rs").write_text(
            "//! Dev-only dependency.\n\n#[test]\nfn touches() {\n    tokio::touch();\n}\n")
        locked = run_game(["cargo", "generate-lockfile", "--offline"], root)
        self.assertEqual(locked.returncode, 0, locked.stderr)
        result = self.deps(root)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("architecture: ok", result.stdout)


class WebArchitectureTests(ArchitectureFixture):
    def test_hexagonal_violations_rejected(self):
        cases = [
            ({"domain": {"axum"}}, BANNED, {}),
            ({"api": {"sqlx"}}, BANNED, {}),
            ({"api": {"infra"}}, "api must not depend on workspace crate infra directly", {}),
            ({"domain": {"app"}}, "domain must not depend on workspace crate app directly",
             {"app": {"domain"}}),
            ({"domain": {"helper"}}, "domain must not depend on tokio (domain -> helper -> tokio)",
             {}),
        ]
        for add, needle, drop in cases:
            with self.subTest(add=add):
                self.assert_rejected("web", "hexagonal", needle, add=add, drop=drop,
                                     vendor={"helper": ("tokio",), "tokio": ()})

    def test_layered_violations_rejected(self):
        for add, needle in [({"api": {"sqlx"}}, BANNED), ({"store": {"axum"}}, BANNED),
                            ({"api": {"store"}},
                             "api must not depend on workspace crate store directly"),
                            ({"store": {"service"}},
                             "store must not depend on workspace crate service directly")]:
            with self.subTest(add=add):
                drop = {"service": {"store"}} if "store" in add else None
                self.assert_rejected("web", "layered", needle, add=add, drop=drop)

    def test_two_crate_violations_rejected(self):
        for add, needle in [({"core": {"axum"}}, BANNED),
                            ({"core": {"server"}},
                             "core must not depend on workspace crate server directly")]:
            with self.subTest(add=add):
                drop = {"server": {"core"}} if add == {"core": {"server"}} else None
                self.assert_rejected("web", "two-crate", needle, add=add, drop=drop)


class WebGameArchitectureTests(ArchitectureFixture):
    def test_hexagonal_violations_rejected(self):
        for add, needle in [({"master": {"domain"}},
                             "master must not depend on workspace crate domain directly"),
                            ({"master": {"tokio"}}, "master must not depend on tokio (master -> tokio)"),
                            ({"api": {"infra"}}, "api must not depend on workspace crate infra directly"),
                            ({"domain": {"sqlx"}}, BANNED)]:
            with self.subTest(add=add):
                drop = {"domain": {"master"}} if add == {"master": {"domain"}} else None
                self.assert_rejected("web-game", "hexagonal", needle, add=add, drop=drop)

    def test_load_mutate_save_violations_rejected(self):
        for add, needle in [({"model": {"tokio"}}, "model must not depend on tokio (model -> tokio)"),
                            ({"api": {"store"}}, "api must not depend on workspace crate store directly"),
                            ({"usecase": {"axum"}}, BANNED),
                            ({"api": {"sqlx"}}, BANNED)]:
            with self.subTest(add=add):
                self.assert_rejected("web-game", "load-mutate-save", needle, add=add)


class GameArchitectureTests(ArchitectureFixture):
    def test_sim_room_violations_rejected(self):
        for add, needle in [({"sim": {"tokio"}}, "sim must not depend on tokio (sim -> tokio)"),
                            ({"sim": {"helper"}}, "sim must not depend on tokio (sim -> helper -> tokio)"),
                            ({"sim": {"futures"}}, "sim must not depend on futures (sim -> futures)"),
                            ({"sim": {"room"}}, "sim must not depend on workspace crate room directly"),
                            ({"room": {"axum"}}, BANNED),
                            ({"gateway": {"sqlx"}}, BANNED),
                            ({"store": {"room"}}, "store must not depend on workspace crate room directly")]:
            with self.subTest(add=add):
                drop = {"room": {"sim"}} if add == {"sim": {"room"}} else None
                self.assert_rejected("game", "sim-room", needle, add=add, drop=drop,
                                     vendor={"helper": ("tokio",), "tokio": ()})

    def test_ecs_violations_rejected(self):
        for add, needle in [({"room": {"hecs"}}, BANNED), ({"gateway": {"bevy_ecs"}}, BANNED),
                            ({"sim": {"tokio"}}, "sim must not depend on tokio (sim -> tokio)")]:
            with self.subTest(add=add):
                self.assert_rejected("game", "ecs", needle, add=add)

    def test_minimal_violations_rejected(self):
        for add, needle in [({"rules": {"tokio"}}, "rules must not depend on tokio (rules -> tokio)"),
                            ({"rules": {"axum"}}, BANNED)]:
            with self.subTest(add=add):
                self.assert_rejected("game", "minimal", needle, add=add)


if __name__ == "__main__":
    unittest.main()
