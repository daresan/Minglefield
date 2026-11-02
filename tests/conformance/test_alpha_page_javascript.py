"""Regression guard for the JavaScript actually served by the alpha gateway.

Run with: python -B -m unittest discover -s tests/conformance -p "test_alpha_page_javascript.py" -v
Requires Node.js on PATH. Fail closed if the checker is unavailable.
"""
import re
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "server"))
from private_alpha_gateway import PAGE


class AlphaPageJavascriptTests(unittest.TestCase):
    def test_embedded_javascript_parses(self):
        scripts = re.findall(r"<script[^>]*>(.*?)</script\s*>", PAGE,
                             flags=re.IGNORECASE | re.DOTALL)
        self.assertTrue(scripts, "No embedded script found in served PAGE")
        node = shutil.which("node")
        self.assertIsNotNone(node, "Node.js is required to validate the served UI JavaScript")
        for index, script in enumerate(scripts):
            with self.subTest(script=index):
                result = subprocess.run(
                    [node, "--check", "-"], input=script, text=True,
                    capture_output=True, timeout=20, check=False)
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_tab_navigation_and_global_update_dialog_present(self):
        self.assertIn('id="alphaNav"', PAGE)
        self.assertIn("renderAlphaTabs();", PAGE)
        self.assertIn('id="platformUpdateDialog"', PAGE)
        self.assertIn('id="gameUpdateDialog"', PAGE)
        self.assertIn('id="gameIntegrationUpdateInspect"', PAGE)
        self.assertIn('id="gameIntegrationRegistryInspect"', PAGE)
        game_start = PAGE.index('id="gameProjectPanel"')
        global_dialog = PAGE.index('id="platformUpdateDialog"')
        self.assertLess(global_dialog, game_start,
                        "Global modal must not be nested in the hidden Game tab")


if __name__ == "__main__":
    unittest.main()
