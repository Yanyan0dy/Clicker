from __future__ import annotations

import compileall
import pathlib
import unittest


class CompileSmokeTests(unittest.TestCase):
    def test_sources_compile(self) -> None:
        root = pathlib.Path(__file__).resolve().parents[1]
        ok = compileall.compile_dir(str(root / "clicker"), quiet=1)
        self.assertTrue(ok)
        ok2 = compileall.compile_dir(str(root / "clicker_core"), quiet=1)
        self.assertTrue(ok2)


if __name__ == "__main__":
    unittest.main()

