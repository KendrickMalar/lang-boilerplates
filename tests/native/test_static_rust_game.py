"""Catch missing, non-self-contained, or weakened Rust game-server quality settings."""
import re
import tomllib
import unittest
from pathlib import Path

from tests.native.rust_game_helpers import LEAVES, ROOT

TAURI = ROOT / "rust/tauri"
FILES = ["README.md", "LICENSE", ".editorconfig", ".gitignore", ".node-version",
         "rust-toolchain.toml", "rustfmt.toml", "clippy.toml", "deny.toml", "Cargo.toml",
         ".config/nextest.toml", ".cargo/config.toml", "scripts/check.sh", "check-commit.mjs",
         "package.json", "pnpm-workspace.yaml", ".husky/pre-commit", ".husky/pre-push"]
GROUP = {"level": "deny", "priority": -1}
RESTRICTION = ["unwrap_used", "expect_used", "panic", "todo", "unimplemented", "unreachable",
               "dbg_macro", "print_stdout", "print_stderr", "exit", "get_unwrap",
               "allow_attributes", "allow_attributes_without_reason",
               "undocumented_unsafe_blocks", "mem_forget", "string_slice", "rc_mutex",
               "lossy_float_literal"]
TAURI_LINTS = ["redundant_clone", "assigning_clones", "or_fun_call"]
LICENSES = {"MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "ISC", "Unicode-3.0", "Zlib"}
BANNED = {"bincode", "fred", "poem", "openssl", "openssl-sys"}
REALTIME_LINTS = ["arithmetic_side_effects", "cast_possible_truncation", "cast_sign_loss",
                  "cast_precision_loss", "cast_possible_wrap", "cast_lossless", "as_conversions",
                  "indexing_slicing", "float_cmp"]
REALTIME = ROOT / "rust/game-realtime"
ROOM = ROOT / "rust/game-room"
SOCIAL = ROOT / "rust/game-social"
# Files that differ per leaf; every other file is byte-identical to the realtime leaf.
# package.json differs only in its "name".
PER_LEAF = {"README.md", "Cargo.toml", "clippy.toml", "deny.toml", "scripts/check.sh",
            "package.json"}
REALTIME_ONLY_METHODS = {"std::time::SystemTime::now", "std::time::Instant::now"}


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
                                         (REALTIME / file).read_bytes(), f"{name}: {file}")

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
        for lint in RESTRICTION + TAURI_LINTS:
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

        self.assertEqual(toml(leaf, "rustfmt.toml"), toml(TAURI, "rustfmt.toml"))
        self.assertEqual((leaf / "check-commit.mjs").read_bytes(),
                         (TAURI / "check-commit.mjs").read_bytes())

        self.assertEqual(list(leaf.rglob("*.rs")), [], "no Rust source is distributed")
        self.assertEqual(list(leaf.rglob("Cargo.lock")), [], "no Cargo.lock is distributed")
        for link in re.findall(r"\[[^\]]+\]\(([^)]+)\)", (leaf / "README.md").read_text()):
            if "://" not in link and not link.startswith("#"):
                self.assertTrue((leaf / link).exists(), link)
                self.assertTrue((leaf / link).resolve().is_relative_to(leaf.resolve()), link)

    def test_realtime_rules(self):
        manifest = toml(REALTIME, "Cargo.toml")
        clippy = manifest["workspace"]["lints"]["clippy"]
        for lint in REALTIME_LINTS:
            self.assertEqual(clippy.get(lint), "deny", lint)
        self.assertNotIn("float_arithmetic", clippy, "games need float arithmetic")
        release = manifest["profile"]["release"]
        self.assertEqual(release["lto"], "fat")
        self.assertEqual(release["codegen-units"], 1)

        clippy_conf = toml(REALTIME, "clippy.toml")
        self.assertLessEqual({"std::time::SystemTime::now", "std::time::Instant::now"},
                             disallowed(clippy_conf["disallowed-methods"]))
        self.assertLessEqual({"std::hash::RandomState", "std::collections::hash_map::RandomState",
                              "std::collections::HashMap", "std::collections::HashSet"},
                             disallowed(clippy_conf["disallowed-types"]))

        banned = {entry if isinstance(entry, str) else entry["crate"]
                  for entry in toml(REALTIME, "deny.toml")["bans"]["deny"]}
        self.assertIn("laminar", banned)

    def check_async_leaf(self, leaf: Path, lints: list[str], methods: set[str], ban: str):
        manifest = toml(leaf, "Cargo.toml")
        clippy = manifest["workspace"]["lints"]["clippy"]
        for lint in lints:
            self.assertEqual(clippy.get(lint), "deny", lint)
        for lint in REALTIME_LINTS:
            self.assertNotIn(lint, clippy, f"realtime-only lint: {lint}")
        self.assertNotIn("float_arithmetic", clippy)
        release = manifest["profile"]["release"]
        self.assertNotIn("lto", release)
        self.assertNotIn("codegen-units", release)

        clippy_conf = toml(leaf, "clippy.toml")
        self.assertEqual(disallowed(clippy_conf["disallowed-methods"]),
                         {"std::thread::sleep", "std::process::exit"} | methods)
        self.assertFalse(REALTIME_ONLY_METHODS & disallowed(clippy_conf["disallowed-methods"]))
        self.assertNotIn("disallowed-types", clippy_conf)
        for entry in clippy_conf["disallowed-methods"]:
            if entry["path"] in methods:
                self.assertIs(entry.get("allow-invalid"), True, entry["path"])

        banned = {entry["crate"] for entry in toml(leaf, "deny.toml")["bans"]["deny"]}
        self.assertIn(ban, banned)
        self.assertNotIn("laminar", banned)
        readme = (leaf / "README.md").read_text()
        for text in ["tick", "RandomState", "laminar", "fat"]:
            self.assertNotIn(text, readme, f"realtime-only README text: {text}")

    @staticmethod
    def banned(leaf: Path) -> set[str]:
        return {entry["crate"] for entry in toml(leaf, "deny.toml")["bans"]["deny"]}

    def test_room_rules(self):
        self.check_async_leaf(
            ROOM,
            ["await_holding_lock", "await_holding_refcell_ref", "await_holding_invalid_type",
             "large_futures"],
            {"tokio::sync::mpsc::unbounded_channel", "futures::channel::mpsc::unbounded"},
            "actix")
        self.assertNotIn("SQLX_OFFLINE", (ROOM / "scripts/check.sh").read_text())
        self.assertNotIn("native-tls", self.banned(ROOM))

    def test_social_rules(self):
        self.check_async_leaf(
            SOCIAL, ["await_holding_lock", "await_holding_refcell_ref"],
            {"sqlx::query", "sqlx::query_as", "reqwest::Client::new", "reqwest::get"}, "native-tls")
        self.assertNotIn("actix", self.banned(SOCIAL))
        clippy = toml(SOCIAL, "Cargo.toml")["workspace"]["lints"]["clippy"]
        self.assertNotIn("await_holding_invalid_type", clippy)
        self.assertNotIn("large_futures", clippy)
        script = (SOCIAL / "scripts/check.sh").read_text()
        self.assertIn("SQLX_OFFLINE=${SQLX_OFFLINE:-true}\nexport SQLX_OFFLINE\n", script)
        readme = (SOCIAL / "README.md").read_text()
        for text in ["cargo sqlx prepare", ".sqlx/", "SQLX_OFFLINE=true"]:
            self.assertIn(text, readme)

    def test_push_stages_identical_in_all_leaves(self):
        # Shared check.sh logic is the realtime script except for the social SQLX lines.
        realtime = (REALTIME / "scripts/check.sh").read_text()
        self.assertEqual((ROOM / "scripts/check.sh").read_text(), realtime)
        social = (SOCIAL / "scripts/check.sh").read_text()
        kept = [line for line in social.splitlines(keepends=True)
                if "SQLX" not in line and "sqlx macros check" not in line]
        self.assertEqual("".join(kept), realtime)

    def test_realtime_push_stages(self):
        script = (REALTIME / "scripts/check.sh").read_text()
        for command in [
            'llvm-cov nextest --workspace --locked --no-tests=fail --fail-under-lines "$line_floor"',
            "line_floor=90\n",
            "deny check advisories",
            "build --workspace --locked --release",
        ]:
            self.assertTrue(command in script, command)
        self.assertIn("advisory database could not be fetched (network required)", script)
        readme = (REALTIME / "README.md").read_text()
        for text in ["`line_floor=90`", "line coverage below 90% (--fail-under-lines 90)",
                     "https://github.com/rustsec/advisory-db",
                     "sh scripts/check.sh push", "cargo-llvm-cov | 0.9.1"]:
            self.assertIn(text, readme)


    def test_commit_runs_coverage(self):
        script = (REALTIME / "scripts/check.sh").read_text()
        self.assertIn("commit) stages='format lint deps coverage' ;;", script)
        self.assertIn("push|all) stages='format lint deps coverage advisories build' ;;", script)
        for leaf in (REALTIME, ROOM, SOCIAL):
            with self.subTest(leaf=leaf.name):
                readme = (leaf / "README.md").read_text()
                self.assertIn("sh scripts/check.sh commit   # format → lint → deps → coverage", readme)
                self.assertNotIn("format → lint → deps → test", readme)


if __name__ == "__main__":
    unittest.main()
