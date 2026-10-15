"""Run tests/test_*.py with unittest inside headless Blender. Zero tests fail.

Usage: blender -b --factory-startup --python-exit-code 1 --python scripts/test.py
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    sys.path.insert(0, str(ROOT))
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"), pattern="test_*.py")
    if suite.countTestCases() == 0:
        print("FAIL no tests found under tests/")
        return 1
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
