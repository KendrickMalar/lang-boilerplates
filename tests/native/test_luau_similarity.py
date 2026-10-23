"""Private CLI integration: explicit preinstalled release only, never automatic download."""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

from tests.native.roblox_helpers import copy_fixture, roblox_env, run_check

BINARY_SHA = "01487746514f5b1ff9833431c7e1da8a54fa120594d82c1831d894ea07f64eab"


def uninstalled_fixture(name: str) -> Path:
    return copy_fixture(name, similarity=False)


def install_test_binary(root: Path) -> Path:
    supplied = os.environ.get("LUAU_SIMILARITY_BINARY")
    if not supplied:
        raise RuntimeError("explicit LUAU_SIMILARITY_BINARY required; obtain approved private release first")
    source = Path(supplied)
    if source.is_symlink() or not source.is_file() or hashlib.sha256(source.read_bytes()).hexdigest() != BINARY_SHA:
        raise RuntimeError("preinstalled similarity release is missing or hash differs")
    target = root / ".tools/luau-similarity"
    target.mkdir(parents=True, exist_ok=False)
    binary = target / "luau-similarity"
    shutil.copy2(source, binary)
    lock_sha = hashlib.sha256((root / "luau-similarity.lock.json").read_bytes()).hexdigest()
    (target / "installation.json").write_text(json.dumps({"schema": 1, "lock_sha256": lock_sha,
                                                        "binary_sha256": BINARY_SHA}))
    return binary


class LuauSimilarityTests(unittest.TestCase):
    def run_verify(self, root: Path, mode: str | None = None, cwd: Path | None = None):
        args = ["lune", "run", str(root / "scripts/verify-similarity.luau")]
        if mode:
            args.append(mode)
        return subprocess.run(args, cwd=cwd or root, env=roblox_env(root), text=True,
                              capture_output=True, check=False)

    def test_actual_preinstalled_release_passes_verification(self):
        root = uninstalled_fixture("similarity-valid")
        binary = install_test_binary(root)
        before = binary.read_bytes()
        result = self.run_verify(root)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("verified", result.stdout)
        self.assertEqual(binary.read_bytes(), before)

    def test_missing_installation_is_failure(self):
        root = uninstalled_fixture("similarity-missing")
        result = self.run_verify(root)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("not installed", result.stdout + result.stderr)
        self.assertFalse((root / ".tools").exists())

    def test_tampered_binary_is_not_executed_or_restored(self):
        root = uninstalled_fixture("similarity-corrupt")
        binary = install_test_binary(root)
        binary.write_bytes(b"untrusted binary")
        result = self.run_verify(root)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("hash", result.stdout + result.stderr)
        self.assertEqual(binary.read_bytes(), b"untrusted binary")

    def test_symlink_installation_is_refused_without_following_it(self):
        root = uninstalled_fixture("similarity-link")
        other = root / "outside"
        other.mkdir()
        (root / ".tools").symlink_to(other, target_is_directory=True)
        result = self.run_verify(root)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("symlink", result.stdout + result.stderr)
        self.assertEqual(list(other.iterdir()), [])

    def test_script_from_another_project_cannot_select_cwd(self):
        root = uninstalled_fixture("similarity-root")
        install_test_binary(root)
        other = uninstalled_fixture("similarity-other")
        install_test_binary(other)
        result = self.run_verify(root, cwd=other)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("project root", result.stdout + result.stderr)

    def test_similarity_stage_uses_actual_cli_without_network(self):
        root = uninstalled_fixture("similarity-stage")
        install_test_binary(root)
        result = run_check(root, "similarity")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("stage: similarity", result.stdout)
        self.assertIn("matches", result.stdout.lower())




    def test_version_permission_and_zero_source_fail_closed(self):
        for defect in ["version", "permission", "source"]:
            with self.subTest(defect=defect):
                root = uninstalled_fixture("similarity-" + defect)
                binary = install_test_binary(root)
                if defect == "version":
                    file = root / "luau-similarity.lock.json"
                    lock = json.loads(file.read_text())
                    lock.update(version="0.2.0", tag="v0.2.0",
                                asset="luau-similarity-v0.2.0-aarch64-apple-darwin.tar.gz",
                                mpl_source_asset="luau-similarity-v0.2.0-mpl-sources.tar.gz")
                    file.write_text(json.dumps(lock))
                    receipt = binary.parent / "installation.json"
                    value = json.loads(receipt.read_text())
                    value["lock_sha256"] = hashlib.sha256(file.read_bytes()).hexdigest()
                    receipt.write_text(json.dumps(value))
                elif defect == "permission":
                    binary.chmod(0o600)
                else:
                    (root / "src/shared/Greeting.luau").unlink()
                result = run_check(root, "similarity") if defect == "source" else self.run_verify(root)
                self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(hashlib.sha256(binary.read_bytes()).hexdigest(), BINARY_SHA)



    def test_all_preflight_rejects_missing_cli_before_expensive_stages(self):
        root = uninstalled_fixture("similarity-preflight")
        result = run_check(root, "all")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("not installed", result.stdout + result.stderr)
        self.assertNotIn("stage: format", result.stdout + result.stderr)


class LuauHelperQualityTests(unittest.TestCase):
    def test_lune_helper_type_error_blocks_typecheck(self):
        root = copy_fixture("helper-type")
        (root / "scripts/Broken.luau").write_text('--!strict\nlocal value: number = "bad"\nreturn value\n')
        result = run_check(root, "typecheck")
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Broken.luau", result.stdout + result.stderr)


class LuauSimilaritySetupTests(unittest.TestCase):
    def setup_run(self, root: Path, denied: bool = False):
        archive = os.environ.get("LUAU_SIMILARITY_ARCHIVE")
        if not archive:
            raise RuntimeError("explicit LUAU_SIMILARITY_ARCHIVE required")
        fake_dir = root / ".verification/fake-bin"
        fake_dir.mkdir(parents=True)
        fake = fake_dir / "gh"
        code = (
            f"#!{sys.executable}\nimport os,pathlib,shutil,sys\n"
            "assert os.environ['GH_HOST']=='github.com'\n"
            "assert sys.argv[1:3]==['release','download']\n"
            "assert sys.argv[sys.argv.index('--repo')+1]=='github.com/KendrickMalar/luau-similarity'\n"
            f"denied={denied!r}\n"
            "if denied:\n print(os.environ['GH_TOKEN'],file=sys.stderr)\n sys.exit(1)\n"
            f"source=pathlib.Path({archive!r})\n"
            "dest=pathlib.Path(sys.argv[sys.argv.index('--dir')+1])\n"
            "pattern=sys.argv[sys.argv.index('--pattern')+1]\n"
            "assert pattern==source.name\nshutil.copy2(source,dest/pattern)\n"
        )
        fake.write_text(code)
        fake.chmod(0o700)
        env = roblox_env(root)
        env["PATH"] = str(fake_dir) + os.pathsep + env["PATH"]
        env["GH_HOST"] = "unapproved.example.invalid"
        env["GH_TOKEN"] = "fixture-private-token-do-not-print"
        result = subprocess.run(["lune", "run", str(root / "scripts/setup-similarity.luau")],
                                cwd=root, env=env, text=True, capture_output=True, check=False)
        self.assertNotIn(env["GH_TOKEN"], result.stdout + result.stderr)
        return result

    def test_explicit_setup_uses_fixed_host_and_verifies_real_archive(self):
        root = uninstalled_fixture("similarity-setup")
        result = self.setup_run(root)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        binary = root / ".tools/luau-similarity/luau-similarity"
        self.assertEqual(hashlib.sha256(binary.read_bytes()).hexdigest(), BINARY_SHA)
        self.assertTrue((binary.parent / "lune-types/fs.luau").is_file())

    def test_access_failure_preserves_partial_directory_and_no_token(self):
        root = uninstalled_fixture("similarity-denied")
        result = self.setup_run(root, denied=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("private release access failed", result.stdout + result.stderr)
        self.assertTrue((root / ".tools/luau-similarity").is_dir())
        self.assertFalse((root / ".tools/luau-similarity/installation.json").exists())




    def test_unknown_existing_directory_is_not_repaired_or_overwritten(self):
        root = uninstalled_fixture("similarity-unknown")
        directory = root / ".tools/luau-similarity"
        directory.mkdir(parents=True)
        keep = directory / "keep"
        keep.write_bytes(b"unknown user bytes")
        result = self.setup_run(root)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("existing installation", result.stdout + result.stderr)
        self.assertEqual(keep.read_bytes(), b"unknown user bytes")
        self.assertEqual([p.name for p in directory.iterdir()], ["keep"])



    def test_archive_hash_failure_never_extracts_or_retries(self):
        from unittest.mock import patch
        root = uninstalled_fixture("similarity-badarchive")
        bad = root / ".verification/bad/luau-similarity-v0.1.0-aarch64-apple-darwin.tar.gz"
        bad.parent.mkdir(parents=True)
        bad.write_bytes(b"not the approved archive")
        with patch.dict(os.environ, {"LUAU_SIMILARITY_ARCHIVE": str(bad)}):
            result = self.setup_run(root)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("archive hash mismatch", result.stdout + result.stderr)
        directory = root / ".tools/luau-similarity"
        self.assertFalse((directory / "luau-similarity").exists())
        self.assertEqual((directory / "download" / bad.name).read_bytes(), bad.read_bytes())


class LuauGitGateTests(unittest.TestCase):
    def git_run(self, root: Path, env: dict[str, str], *args: str):
        return subprocess.run(["git", *args], cwd=root, env=env, text=True, capture_output=True, check=False)

    def git_fixture(self):
        root = copy_fixture("full-git")
        env = roblox_env(root)
        env.update(GIT_CONFIG_GLOBAL="/dev/null", GIT_CONFIG_NOSYSTEM="1",
                   GIT_AUTHOR_NAME="Fixture", GIT_AUTHOR_EMAIL="fixture@example.invalid",
                   GIT_COMMITTER_NAME="Fixture", GIT_COMMITTER_EMAIL="fixture@example.invalid")
        for args in [("init", "-q", "--initial-branch=feat/fixture"),
                     ("config", "--local", "core.hooksPath", str(root / ".githooks"))]:
            result = self.git_run(root, env, *args)
            self.assertEqual(result.returncode, 0, result.stderr)
        (root / "README.fixture").write_text("baseline\n")
        self.assertEqual(self.git_run(root, env, "add", ".").returncode, 0)
        return root, env

    def test_commit_runs_every_stage_not_only_format_and_lint(self):
        root, env = self.git_fixture()
        result = self.git_run(root, env, "commit", "-m", "full gate")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        for stage in ["format", "lint", "typecheck", "test", "build", "similarity"]:
            self.assertIn("stage: " + stage, result.stdout + result.stderr)

    def test_hidden_index_flag_blocks_commit_and_keeps_head(self):
        root, env = self.git_fixture()
        first = self.git_run(root, env, "commit", "-m", "baseline")
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        head = self.git_run(root, env, "rev-parse", "HEAD").stdout
        self.assertEqual(self.git_run(root, env, "update-index", "--assume-unchanged", "README.fixture").returncode, 0)
        (root / "README.fixture").write_text("hidden change\n")
        (root / "another.txt").write_text("staged change\n")
        self.assertEqual(self.git_run(root, env, "add", "another.txt").returncode, 0)
        result = self.git_run(root, env, "commit", "-m", "must reject")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("hidden", result.stdout + result.stderr)
        self.assertEqual(self.git_run(root, env, "rev-parse", "HEAD").stdout, head)
        self.assertEqual((root / "README.fixture").read_text(), "hidden change\n")



    def test_hook_from_another_project_cannot_execute_its_cwd(self):
        source, _ = self.git_fixture()
        other, env = self.git_fixture()
        result = subprocess.run([str(source / ".githooks/pre-commit")], cwd=other, env=env,
                                text=True, capture_output=True, check=False)
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("project root", result.stdout + result.stderr)



    def commit_baseline(self, root: Path, env: dict[str, str]) -> str:
        result = self.git_run(root, env, "commit", "-m", "baseline")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return self.git_run(root, env, "rev-parse", "HEAD").stdout.strip()

    def bare_remote(self, root: Path, env: dict[str, str]) -> Path:
        remote = root.parent / "remote.git"
        result = self.git_run(root, env, "init", "--bare", "-q", str(remote))
        self.assertEqual(result.returncode, 0, result.stderr)
        return remote

    def test_normal_push_and_different_commit_push(self):
        root, env = self.git_fixture()
        first = self.commit_baseline(root, env)
        remote = self.bare_remote(root, env)
        result = self.git_run(root, env, "push", str(remote), "HEAD:refs/heads/fixture")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("stage: similarity", result.stdout + result.stderr)
        pinned = self.git_run(root, env, "push", str(remote), first + ":refs/heads/pinned")
        self.assertEqual(pinned.returncode, 0, pinned.stdout + pinned.stderr)
        (root / "another.txt").write_text("second\n")
        self.assertEqual(self.git_run(root, env, "add", "another.txt").returncode, 0)
        second = self.commit_baseline(root, env)
        self.assertNotEqual(first, second)
        result = self.git_run(root, env, "push", str(remote), first + ":refs/heads/old")
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("checked HEAD", result.stdout + result.stderr)
        remote_ref = self.git_run(root, env, "--git-dir=" + str(remote), "rev-parse", "refs/heads/fixture")
        self.assertEqual(remote_ref.stdout.strip(), first)
        self.assertNotEqual(self.git_run(root, env, "--git-dir=" + str(remote), "show-ref", "--verify", "refs/heads/old").returncode, 0)

    def test_source_and_index_mutation_during_checks_block_commit(self):
        for stage_index in [False, True]:
            with self.subTest(stage_index=stage_index):
                root, env = self.git_fixture()
                head = self.commit_baseline(root, env)
                (root / "another.txt").write_text("staged\n")
                self.assertEqual(self.git_run(root, env, "add", "another.txt").returncode, 0)
                fake_dir = root / ".verification/mutator"
                fake_dir.mkdir()
                real = shutil.which("selene", path=env["PATH"])
                self.assertIsNotNone(real)
                fake = fake_dir / "selene"
                fake.write_text("#!/bin/sh\n" + repr(real) + ' "$@"\nstatus=$?\n[ "$status" -eq 0 ] || exit "$status"\n'
                                'case "$1" in --version) exit 0 ;; esac\n'
                                "printf 'changed during check\\n' > README.fixture\n"
                                + ("git add README.fixture\n" if stage_index else "") + "exit 0\n")
                fake.chmod(0o700)
                env["PATH"] = str(fake_dir) + os.pathsep + env["PATH"]
                result = self.git_run(root, env, "commit", "-m", "must stop mutation")
                self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertTrue("changed during checks" in result.stdout + result.stderr
                                or "unstaged changes" in result.stdout + result.stderr, result.stdout + result.stderr)
                self.assertEqual(self.git_run(root, env, "rev-parse", "HEAD").stdout.strip(), head)
                self.assertEqual((root / "README.fixture").read_text(), "changed during check\n")

    def test_full_commit_blocks_type_test_build_and_clone_failures(self):
        for defect in ["type", "test", "build", "clone"]:
            with self.subTest(defect=defect):
                root, env = self.git_fixture()
                head = self.commit_baseline(root, env)
                if defect == "type":
                    (root / "src/shared/Bad.luau").write_text('--!strict\nlocal n: number = "bad"\n\nreturn n\n')
                elif defect == "test":
                    spec = root / "tests/Greeting.spec.luau"
                    spec.write_text(spec.read_text().replace('"Hello, Roblox!"', '"bad"'))
                elif defect == "build":
                    config = root / "default.project.json"
                    config.write_text(config.read_text().replace('"src/server"', '"src/missing"'))
                else:
                    parts = ["--!strict", "local function calculate(value: number): number"]
                    for i in range(8):
                        parts.append(f"\\tlocal v{i} = value + {i + 1}")
                    parts.append("\\treturn " + " + ".join(f"v{i}" for i in range(8)))
                    parts += ["end", "", "return calculate", ""]
                    code = "\n".join(parts).replace("\\t", "\t")
                    for name in ["CloneA.luau", "CloneB.luau"]:
                        (root / "src/shared" / name).write_text(code)
                    formatted = subprocess.run(["stylua", "src/shared/CloneA.luau", "src/shared/CloneB.luau"],
                                               cwd=root, env=env, capture_output=True, text=True, check=False)
                    self.assertEqual(formatted.returncode, 0, formatted.stderr)
                self.assertEqual(self.git_run(root, env, "add", ".").returncode, 0)
                result = self.git_run(root, env, "commit", "-m", "must block " + defect)
                self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                if defect == "clone":
                    self.assertIn("matches: 1", result.stdout + result.stderr)
                self.assertEqual(self.git_run(root, env, "rev-parse", "HEAD").stdout.strip(), head)



    def test_actual_global_dispatcher_and_linked_worktree(self):
        from tests.native.roblox_helpers import copy_similarity_tool
        from tests.native.test_hooks import global_hooks_snapshot
        outer = Path(__file__).resolve().parents[2]
        outer_config = subprocess.run(["git", "-C", str(outer), "config", "--local", "--get", "core.bare"],
                                      text=True, capture_output=True, check=False).stdout
        before = global_hooks_snapshot()
        actual = Path(os.path.expandvars(os.path.expanduser(before["path"])))
        self.assertTrue(actual.is_dir(), "existing global dispatcher prerequisite missing")
        root, env = self.git_fixture()
        head = self.commit_baseline(root, env)
        fake_global = root.parent / "global-hooks"
        fake_global.mkdir()
        for name in ["pre-commit", "pre-push"]:
            source = actual / name
            self.assertTrue(source.is_file(), "global dispatcher hook prerequisite missing")
            shutil.copy2(source, fake_global / name)
            bridge = root / ".git/hooks" / name
            bridge.write_text('#!/bin/sh\nroot=$(git rev-parse --show-toplevel)\nexec "$root/.githooks/' + name + '" "$@"\n')
            bridge.chmod(0o700)
        config = root.parent / "global.gitconfig"
        config.write_text("[core]\n    hooksPath = " + str(fake_global) + "\n")
        env["GIT_CONFIG_GLOBAL"] = str(config)
        unset = self.git_run(root, env, "config", "--local", "--unset", "core.hooksPath")
        self.assertEqual(unset.returncode, 0, unset.stderr)
        linked = root.parent / "linked"
        add = self.git_run(root, env, "worktree", "add", "-b", "feat/linked", str(linked))
        self.assertEqual(add.returncode, 0, add.stdout + add.stderr)
        copy_similarity_tool(linked)
        (linked / ".luau-lsp-cache").mkdir()
        shutil.copy2(root / ".luau-lsp-cache/globalTypes-1.69.0.d.luau",
                     linked / ".luau-lsp-cache/globalTypes-1.69.0.d.luau")
        linked_env = roblox_env(linked)
        linked_env.update({key: value for key, value in env.items() if key.startswith("GIT_")})
        (linked / "linked.txt").write_text("linked worktree\n")
        self.assertEqual(self.git_run(linked, linked_env, "add", "linked.txt").returncode, 0)
        result = self.git_run(linked, linked_env, "commit", "-m", "linked full gate")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("stage: similarity", result.stdout + result.stderr)
        self.assertNotEqual(self.git_run(linked, linked_env, "rev-parse", "HEAD").stdout.strip(), head)
        remote = self.bare_remote(linked, linked_env)
        result = self.git_run(linked, linked_env, "push", str(remote), "HEAD:refs/heads/linked")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Git source/index guard verified", result.stdout + result.stderr)
        self.assertEqual(global_hooks_snapshot(), before)
        after_config = subprocess.run(["git", "-C", str(outer), "config", "--local", "--get", "core.bare"],
                                     text=True, capture_output=True, check=False).stdout
        self.assertEqual(after_config, outer_config)
        self.assertEqual(self.git_run(root, env, "config", "--local", "--get", "core.bare").stdout.strip(), "false")



    def test_skip_worktree_untracked_and_unstaged_block_without_mutation(self):
        for defect in ["skip", "untracked", "unstaged"]:
            with self.subTest(defect=defect):
                root, env = self.git_fixture()
                head = self.commit_baseline(root, env)
                (root / "staged.txt").write_text("staged\n")
                self.assertEqual(self.git_run(root, env, "add", "staged.txt").returncode, 0)
                if defect == "skip":
                    self.assertEqual(self.git_run(root, env, "update-index", "--skip-worktree", "README.fixture").returncode, 0)
                    (root / "README.fixture").write_text("hidden\n")
                elif defect == "untracked":
                    (root / "unknown.txt").write_text("keep unknown\n")
                else:
                    (root / "README.fixture").write_text("unstaged\n")
                result = self.git_run(root, env, "commit", "-m", "must reject " + defect)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(self.git_run(root, env, "rev-parse", "HEAD").stdout.strip(), head)
                if defect == "untracked":
                    self.assertEqual((root / "unknown.txt").read_text(), "keep unknown\n")


if __name__ == "__main__":
    unittest.main()
