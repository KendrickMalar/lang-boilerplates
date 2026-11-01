"""Real Git/Lune snapshot boundary; no native build, API, download or hook recursion."""
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class HuskyGitStateTests(unittest.TestCase):
    def test_snapshot_requires_husky_and_node_inputs_to_be_tracked(self):
        lune = os.environ.get('LUNE_BIN')
        self.assertTrue(lune and Path(lune).is_file(), 'explicit preinstalled LUNE_BIN required')
        version = subprocess.run([lune, '--version'], text=True, capture_output=True)
        self.assertEqual(version.returncode, 0, version.stderr)
        self.assertEqual(version.stdout.strip(), 'lune 0.10.5')
        parent = ROOT / '.verification/native/husky-git-state'
        parent.mkdir(parents=True, exist_ok=True)
        root = Path(tempfile.mkdtemp(prefix='snapshot-', dir=parent)) / 'project'
        shutil.copytree(ROOT / 'roblox/roblox-game', root)
        # Snapshot only checks tracked inputs. These are not compiler/test fixtures.
        (root / 'roblox.yml').write_text('# snapshot-only fixture\n')
        (root / 'pnpm-lock.yaml').write_text('# snapshot-only fixture, never used to install\n')
        probe = root / '.verification/probe.luau'
        probe.parent.mkdir()
        probe.write_text('local Git = require("../scripts/git-state")\nGit.snapshot(false)\nprint("snapshot accepted")\n')
        env = {key: value for key, value in os.environ.items() if not key.startswith('GIT_')}
        home = root.parent / 'home'
        home.mkdir()
        env.update(HOME=str(home), XDG_CONFIG_HOME=str(home / '.config'),
                   GIT_CONFIG_GLOBAL='/dev/null', GIT_CONFIG_NOSYSTEM='1')

        def git(*args):
            result = subprocess.run(['git', *args], cwd=root, env=env, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            return result

        def snapshot():
            return subprocess.run([lune, 'run', str(probe)], cwd=root, env=env,
                                  text=True, capture_output=True, timeout=30)

        git('init', '-q')
        git('add', '.')
        accepted = snapshot()
        self.assertEqual(accepted.returncode, 0, accepted.stdout + accepted.stderr)
        self.assertIn('snapshot accepted', accepted.stdout)
        for name in ['.husky/pre-commit', '.husky/pre-push', 'package.json',
                     'pnpm-workspace.yaml', 'pnpm-lock.yaml', 'check-commit.mjs']:
            with self.subTest(input=name):
                # Remove only the fixture's index entry, retaining bytes and hiding the
                # resulting untracked file to reach the REQUIRED-input check itself.
                git('update-index', '--force-remove', '--', name)
                (root / '.git/info/exclude').write_text('\n/' + name + '\n')
                rejected = snapshot()
                self.assertNotEqual(rejected.returncode, 0, rejected.stdout + rejected.stderr)
                self.assertIn('check input must be tracked/staged: ' + name,
                              rejected.stdout + rejected.stderr)
                (root / '.git/info/exclude').write_text('')
                git('add', '--', name)
                restored = snapshot()
                self.assertEqual(restored.returncode, 0, restored.stdout + restored.stderr)


if __name__ == '__main__':
    unittest.main()
