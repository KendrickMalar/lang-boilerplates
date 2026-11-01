"""Catch missing, non-self-contained, or weakened Rust server quality settings."""
import re
import tomllib
import unittest
from pathlib import Path

from tests.native.rust_game_helpers import LEAVES, ROOT

FILES = ["README.md", "LICENSE", ".editorconfig", ".gitignore", ".node-version",
         "rust-toolchain.toml", "rustfmt.toml", "clippy.toml", "deny.toml", "Cargo.toml",
         ".config/nextest.toml", ".cargo/config.toml", "scripts/check.sh",
         "scripts/check-architecture.sh", "check-commit.mjs",
         "package.json", "pnpm-workspace.yaml", ".husky/pre-commit", ".husky/pre-push"]
GROUP = {"level": "deny", "priority": -1}
RESTRICTION = ["unwrap_used", "expect_used", "panic", "todo", "unimplemented", "unreachable",
               "dbg_macro", "print_stdout", "print_stderr", "exit", "get_unwrap",
               "allow_attributes", "allow_attributes_without_reason",
               "undocumented_unsafe_blocks", "mem_forget", "string_slice", "rc_mutex",
               "lossy_float_literal"]
CLONE_LINTS = ["redundant_clone", "assigning_clones", "or_fun_call"]
LICENSES = {"MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "ISC", "Unicode-3.0", "Zlib"}
BANNED = {"bincode", "fred", "poem", "openssl", "openssl-sys"}
REALTIME_LINTS = ["arithmetic_side_effects", "cast_possible_truncation", "cast_sign_loss",
                  "cast_precision_loss", "cast_possible_wrap", "cast_lossless", "as_conversions",
                  "indexing_slicing", "float_cmp"]
GAME = ROOT / "rust/game"
WEB_GAME = ROOT / "rust/web-game"
WEB = ROOT / "rust/web"
# Files that differ per leaf; every other file is byte-identical to the game leaf.
# package.json differs only in its "name".
PER_LEAF = {"README.md", "Cargo.toml", "clippy.toml", "deny.toml", "scripts/check.sh",
            "package.json"}
GAME_ONLY_METHODS = {"std::time::SystemTime::now", "std::time::Instant::now"}
ROOM_LINTS = ["await_holding_lock", "await_holding_refcell_ref", "await_holding_invalid_type",
              "large_futures"]
ROOM_METHODS = {"tokio::sync::mpsc::unbounded_channel", "futures::channel::mpsc::unbounded"}
API_METHODS = {"sqlx::query", "sqlx::query_as", "reqwest::Client::new", "reqwest::get"}


def toml(leaf: Path, name: str) -> dict:
    return tomllib.loads((leaf / name).read_text())


def disallowed(entries: list) -> set[str]:
    return {entry if isinstance(entry, str) else entry["path"] for entry in entries}


class StaticRustGameTests(unittest.TestCase):
    def test_common_contract(self):
        for name in LEAVES:
            with self.subTest(leaf=name):
                leaf = ROOT / "rust" / name
                missing = [file for file in FILES if not (leaf / file).is_file()]
                self.assertEqual(missing, [], f"{name}: missing settings")
                self.check_common(leaf)
                for file in FILES:
                    if file not in PER_LEAF:
                        self.assertEqual((leaf / file).read_bytes(),
                                         (GAME / file).read_bytes(), f"{name}: {file}")

    def check_common(self, leaf: Path):
        toolchain = toml(leaf, "rust-toolchain.toml")["toolchain"]
        self.assertEqual(toolchain["channel"], "1.99.1")
        self.assertEqual(set(toolchain["components"]), {"rustfmt", "clippy", "llvm-tools"})
        self.assertEqual(toolchain["profile"], "minimal")

        manifest = toml(leaf, "Cargo.toml")
        self.assertNotIn("package", manifest)
        workspace = manifest["workspace"]
        self.assertEqual(workspace["resolver"], "3")
        self.assertEqual(workspace["members"], ["crates/*"])
        package = workspace["package"]
        self.assertEqual(package["edition"], "2024")
        self.assertEqual(package["rust-version"], "1.99")
        self.assertIs(package["publish"], False)

        rust = workspace["lints"]["rust"]
        self.assertEqual(rust["unsafe_code"], "forbid")
        for lint in ["missing_docs", "unused_must_use", "unreachable_pub", "unused_qualifications"]:
            self.assertEqual(rust[lint], "deny", lint)
        self.assertEqual(rust["rust_2018_idioms"], GROUP)
        clippy = workspace["lints"]["clippy"]
        for group in ["all", "pedantic", "nursery", "cargo"]:
            self.assertEqual(clippy[group], GROUP, group)
        for lint in RESTRICTION + CLONE_LINTS:
            self.assertEqual(clippy.get(lint), "deny", lint)

        release = manifest["profile"]["release"]
        self.assertIs(release["overflow-checks"], True)
        self.assertEqual(release["debug"], "line-tables-only")
        self.assertEqual(release["panic"], "unwind")

        clippy_conf = toml(leaf, "clippy.toml")
        for key in ["allow-unwrap-in-tests", "allow-expect-in-tests", "allow-panic-in-tests",
                    "allow-print-in-tests"]:
            self.assertIs(clippy_conf[key], True, key)
        self.assertLessEqual({"std::thread::sleep", "std::process::exit"},
                             disallowed(clippy_conf["disallowed-methods"]))

        deny = toml(leaf, "deny.toml")
        self.assertEqual(set(deny["licenses"]["allow"]), LICENSES)
        self.assertIs(deny["licenses"]["private"]["ignore"], True)
        self.assertEqual(deny["bans"]["multiple-versions"], "deny")
        self.assertEqual(deny["bans"]["wildcards"], "deny")
        banned = {entry if isinstance(entry, str) else entry["crate"]
                  for entry in deny["bans"]["deny"]}
        self.assertLessEqual(BANNED, banned)
        self.assertEqual(deny["sources"]["unknown-registry"], "deny")
        self.assertEqual(deny["sources"]["unknown-git"], "deny")

        self.assertEqual(toml(leaf, "rustfmt.toml"),
                         {"edition": "2024", "max_width": 100, "tab_spaces": 4, "hard_tabs": False,
                          "newline_style": "Unix", "reorder_imports": True})
        # Every native leaf shares one commit gate.
        self.assertEqual((leaf / "check-commit.mjs").read_bytes(),
                         (ROOT / "swift/macos/check-commit.mjs").read_bytes())

        self.assertEqual(list(leaf.rglob("*.rs")), [], "no Rust source is distributed")
        self.assertEqual(list(leaf.rglob("Cargo.lock")), [], "no Cargo.lock is distributed")
        for link in re.findall(r"\[[^\]]+\]\(([^)]+)\)", (leaf / "README.md").read_text()):
            if "://" not in link and not link.startswith("#"):
                self.assertTrue((leaf / link).exists(), link)
                self.assertTrue((leaf / link).resolve().is_relative_to(leaf.resolve()), link)

    def test_game_rules(self):
        # Deterministic simulation (former game-realtime) plus async rooms (former game-room).
        manifest = toml(GAME, "Cargo.toml")
        clippy = manifest["workspace"]["lints"]["clippy"]
        for lint in REALTIME_LINTS + ROOM_LINTS:
            self.assertEqual(clippy.get(lint), "deny", lint)
        self.assertNotIn("float_arithmetic", clippy, "games need float arithmetic")
        release = manifest["profile"]["release"]
        self.assertEqual(release["lto"], "fat")
        self.assertEqual(release["codegen-units"], 1)

        clippy_conf = toml(GAME, "clippy.toml")
        self.assertEqual(disallowed(clippy_conf["disallowed-methods"]),
                         {"std::thread::sleep", "std::process::exit"} | GAME_ONLY_METHODS
                         | ROOM_METHODS)
        for entry in clippy_conf["disallowed-methods"]:
            if entry["path"] in ROOM_METHODS:
                self.assertIs(entry.get("allow-invalid"), True, entry["path"])
        self.assertLessEqual({"std::hash::RandomState", "std::collections::hash_map::RandomState",
                              "std::collections::HashMap", "std::collections::HashSet"},
                             disallowed(clippy_conf["disallowed-types"]))

        banned = self.banned(GAME)
        self.assertLessEqual({"laminar", "actix"}, banned)
        self.assertNotIn("native-tls", banned)
        self.assertNotIn("SQLX_OFFLINE", (GAME / "scripts/check.sh").read_text())
        readme = (GAME / "README.md").read_text()
        for text in ["リアルタイム対戦", "ルーム制", "WebSocket", "tick", "RandomState", "JoinSet",
                     "unbounded_channel", "actix"]:
            self.assertIn(text, readme)

    def check_async_leaf(self, leaf: Path, lints: list[str], methods: set[str], ban: str):
        manifest = toml(leaf, "Cargo.toml")
        clippy = manifest["workspace"]["lints"]["clippy"]
        for lint in lints:
            self.assertEqual(clippy.get(lint), "deny", lint)
        for lint in REALTIME_LINTS:
            self.assertNotIn(lint, clippy, f"game-only lint: {lint}")
        self.assertNotIn("float_arithmetic", clippy)
        release = manifest["profile"]["release"]
        self.assertNotIn("lto", release)
        self.assertNotIn("codegen-units", release)

        clippy_conf = toml(leaf, "clippy.toml")
        self.assertEqual(disallowed(clippy_conf["disallowed-methods"]),
                         {"std::thread::sleep", "std::process::exit"} | methods)
        self.assertFalse(GAME_ONLY_METHODS & disallowed(clippy_conf["disallowed-methods"]))
        self.assertNotIn("disallowed-types", clippy_conf)
        for entry in clippy_conf["disallowed-methods"]:
            if entry["path"] in methods:
                self.assertIs(entry.get("allow-invalid"), True, entry["path"])

        banned = {entry["crate"] for entry in toml(leaf, "deny.toml")["bans"]["deny"]}
        self.assertIn(ban, banned)
        self.assertNotIn("laminar", banned)
        readme = (leaf / "README.md").read_text()
        for text in ["tick", "RandomState", "laminar", "fat"]:
            self.assertNotIn(text, readme, f"game-only README text: {text}")

    @staticmethod
    def banned(leaf: Path) -> set[str]:
        return {entry["crate"] for entry in toml(leaf, "deny.toml")["bans"]["deny"]}

    def check_api_leaf(self, leaf: Path):
        self.check_async_leaf(leaf, ["await_holding_lock", "await_holding_refcell_ref"],
                              API_METHODS, "native-tls")
        self.assertNotIn("actix", self.banned(leaf))
        clippy = toml(leaf, "Cargo.toml")["workspace"]["lints"]["clippy"]
        self.assertNotIn("await_holding_invalid_type", clippy)
        self.assertNotIn("large_futures", clippy)
        script = (leaf / "scripts/check.sh").read_text()
        self.assertIn("SQLX_OFFLINE=${SQLX_OFFLINE:-true}\nexport SQLX_OFFLINE\n", script)
        readme = (leaf / "README.md").read_text()
        for text in ["cargo sqlx prepare", ".sqlx/", "SQLX_OFFLINE=true"]:
            self.assertIn(text, readme)

    def test_web_game_rules(self):
        self.check_api_leaf(WEB_GAME)
        self.assertIn("ソシャゲ", (WEB_GAME / "README.md").read_text())

    def test_web_rules(self):
        # The generic HTTP API leaf keeps every API rule of web-game; only the README differs.
        self.check_api_leaf(WEB)
        for file in ["Cargo.toml", "clippy.toml", "deny.toml", "scripts/check.sh"]:
            self.assertEqual((WEB / file).read_bytes(), (WEB_GAME / file).read_bytes(), file)
        readme = (WEB / "README.md").read_text()
        for text in ["ソシャゲ型 API", "ランキング", "ガチャ", "マスターデータ"]:
            self.assertNotIn(text, readme, f"web-game-only README text: {text}")
        self.assertIn("HTTP API", readme)

    def test_push_stages_identical_in_all_leaves(self):
        # Shared check.sh logic is the game script except for the API leaves' SQLX lines.
        game = (GAME / "scripts/check.sh").read_text()
        for leaf in (WEB_GAME, WEB):
            with self.subTest(leaf=leaf.name):
                api = (leaf / "scripts/check.sh").read_text()
                kept = [line for line in api.splitlines(keepends=True)
                        if "SQLX" not in line and "sqlx macros check" not in line]
                self.assertEqual("".join(kept), game)

    def test_game_push_stages(self):
        script = (GAME / "scripts/check.sh").read_text()
        for command in [
            'llvm-cov nextest --workspace --locked --no-tests=fail --fail-under-lines "$line_floor"',
            "line_floor=90\n",
            "deny check advisories",
            "build --workspace --locked --release",
        ]:
            self.assertTrue(command in script, command)
        self.assertIn("advisory database could not be fetched (network required)", script)
        readme = (GAME / "README.md").read_text()
        for text in ["`line_floor=90`", "line coverage below 90% (--fail-under-lines 90)",
                     "https://github.com/rustsec/advisory-db",
                     "sh scripts/check.sh push", "cargo-llvm-cov | 0.9.1"]:
            self.assertIn(text, readme)


    def test_commit_runs_coverage(self):
        script = (GAME / "scripts/check.sh").read_text()
        self.assertIn("commit) stages='format lint deps coverage' ;;", script)
        self.assertIn("push|all) stages='format lint deps coverage advisories build' ;;", script)
        for leaf in (GAME, WEB_GAME, WEB):
            with self.subTest(leaf=leaf.name):
                readme = (leaf / "README.md").read_text()
                self.assertIn("sh scripts/check.sh commit   # format → lint → deps → coverage", readme)
                self.assertNotIn("format → lint → deps → test", readme)
                # Binary-only crates: main() is never run by tests and counts against the floor.
                self.assertIn("`main.rs` は数行", readme)


# Architecture choices per leaf; the first one is the default.
CHOICES = {"web": ["hexagonal", "layered", "two-crate"],
           "web-game": ["hexagonal", "load-mutate-save"],
           "game": ["sim-room", "ecs", "minimal"]}
CHOICE_TITLES = {"hexagonal": "軽ヘキサゴナル", "layered": "3層", "two-crate": "2クレート",
                 "load-mutate-save": "プレイヤー単位の読込・純粋変更・保存",
                 "sim-room": "純粋 sim＋ルーム actor", "ecs": "ECS の核", "minimal": "最小"}


def layers(path: Path) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    """architecture/<choice>/layers.conf as ({crate: uses}, {crate: never})."""
    uses: dict[str, set[str]] = {}
    never: dict[str, set[str]] = {}
    for line in path.read_text().splitlines():
        words = line.split("#", 1)[0].split()
        if not words:
            continue
        crate, key, *names = words
        {"uses": uses, "never": never}[key].setdefault(crate, set()).update(names)
    return uses, never


class StaticRustArchitectureTests(unittest.TestCase):
    """README `## アーキテクチャ` and the per-choice enforcement files stay in sync."""

    def section(self, leaf: str, choice: str) -> str:
        readme = (ROOT / "rust" / leaf / "README.md").read_text()
        body = readme.split("\n## アーキテクチャ\n", 1)[1].split("\n## ", 1)[0]
        title = CHOICE_TITLES[choice]
        default = "（既定）" if CHOICES[leaf][0] == choice else ""
        head = f"\n### {title}{default}\n"
        self.assertIn(head, body, f"{leaf}: {head.strip()}")
        return body.split(head, 1)[1].split("\n### ", 1)[0]

    def test_section_order_and_selection_questions(self):
        for leaf, choices in CHOICES.items():
            with self.subTest(leaf=leaf):
                readme = (ROOT / "rust" / leaf / "README.md").read_text()
                self.assertIn("\n## アーキテクチャ\n", readme)
                body = readme.split("\n## アーキテクチャ\n", 1)[1].split("\n## ", 1)[0]
                heads = re.findall(r"^### (.+)$", body, re.MULTILINE)
                self.assertEqual(heads[0], "選び方")
                expected = [CHOICE_TITLES[c] + ("（既定）" if i == 0 else "")
                            for i, c in enumerate(choices)]
                self.assertEqual(heads[1:], expected)
                self.assertIn("scaffold", body.split("\n### ", 1)[0])

    def test_choice_files_are_self_contained_and_parse(self):
        for leaf, choices in CHOICES.items():
            base = ROOT / "rust" / leaf / "architecture"
            with self.subTest(leaf=leaf):
                self.assertEqual(sorted(p.name for p in base.iterdir()), sorted(choices))
            for choice in choices:
                with self.subTest(leaf=leaf, choice=choice):
                    files = sorted(p.name for p in (base / choice).iterdir())
                    self.assertEqual(files, ["deny.toml", "layers.conf"])
                    uses, never = layers(base / choice / "layers.conf")
                    self.assertTrue(uses)
                    self.assertLessEqual(set(never), set(uses), "never for an unlisted crate")
                    for crate, deps in uses.items():
                        self.assertLessEqual(deps, set(uses), f"{crate} uses an unlisted crate")
                        self.assertNotIn(crate, deps)
                    bans = toml(base / choice, "deny.toml")["bans"]
                    self.assertEqual(bans["multiple-versions"], "allow")
                    self.assertEqual(bans["wildcards"], "allow")
                    self.assertTrue(bans["deny"])
                    for entry in bans["deny"]:
                        self.assertTrue(entry["wrappers"], entry["crate"])
                        self.assertLessEqual(set(entry["wrappers"]), set(uses), entry["crate"])
                        self.assertNotIn(entry["crate"], uses, "workspace crates go in layers.conf")
                        self.assertTrue(entry.get("reason"), entry["crate"])

    def test_readme_matches_choice_files(self):
        for leaf, choices in CHOICES.items():
            for choice in choices:
                with self.subTest(leaf=leaf, choice=choice):
                    text = self.section(leaf, choice)
                    for name in ("layers.conf", "deny.toml"):
                        self.assertIn(f"](architecture/{choice}/{name})", text)
                    self.assertIn("MUST NOT", text)
                    self.assertIn("向く", text)
                    self.assertIn("向かない", text)
                    mermaid = re.findall(r"```mermaid\n(.*?)```", text, re.DOTALL)
                    self.assertEqual(len(mermaid), 1)
                    self.assertTrue(mermaid[0].startswith("flowchart"))
                    edges = set(re.findall(r"^\s*([\w-]+) --> ([\w-]+)\s*$", mermaid[0],
                                           re.MULTILINE))
                    uses, _ = layers(ROOT / "rust" / leaf / "architecture" / choice / "layers.conf")
                    expected = {(crate, dep) for crate, deps in uses.items() for dep in deps}
                    self.assertEqual(edges, expected, "mermaid arrows = layers.conf uses")
                    for crate in uses:
                        self.assertIn(f"`{crate}`", text)

    def test_check_runs_architecture_in_deps_stage(self):
        for leaf in CHOICES:
            with self.subTest(leaf=leaf):
                script = (ROOT / "rust" / leaf / "scripts/check.sh").read_text()
                self.assertIn('            "$deny" deny --offline check bans licenses sources\n'
                              '            sh scripts/check-architecture.sh "$deny"\n', script)
                arch = (ROOT / "rust" / leaf / "scripts/check-architecture.sh").read_text()
                self.assertIn("architecture/layers.conf", arch)
                self.assertIn('--config "$bans" check bans', arch)
                self.assertIn("--no-dedupe", arch)
                readme = (ROOT / "rust" / leaf / "README.md").read_text()
                self.assertIn("[scripts/check-architecture.sh](scripts/check-architecture.sh)",
                              readme)


if __name__ == "__main__":
    unittest.main()
