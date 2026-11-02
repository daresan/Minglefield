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

    def test_release_display_uses_text_and_never_signals_verified_current(self):
        start=PAGE.index("function gameUpdateSignal(")
        end=PAGE.index("let gameUpdateRequestId=",start)
        functions=PAGE[start:end]
        script="""
const assert=require('node:assert/strict');
const target={textContent:''};
Object.defineProperty(target,'innerHTML',{set(){throw Error('HTML injection');}});
global.document={getElementById:()=>target};
"""+functions+"""
const item={state:'unknown',comparison_state:'up_to_date',version_scheme:'pep440',
 release_notes:'<img src=x onerror=alert(1)>',verification_state:'unknown'};
renderGameUpdatePreview({updates:[item]},200);
assert.ok(target.textContent.includes(item.release_notes));
assert.ok(target.textContent.includes('up_to_date'));
assert.equal(gameUpdateSignal({updates:[item]},200),'unknown');
assert.equal(gameUpdateSignal({updates:[{...item,version_comparison:'newer_release_than_declared'}]},200),'yellow');
"""
        node=shutil.which("node")
        self.assertIsNotNone(node)
        result=subprocess.run([node,"-"],input=script,text=True,capture_output=True,timeout=20)
        self.assertEqual(result.returncode,0,result.stderr)

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
