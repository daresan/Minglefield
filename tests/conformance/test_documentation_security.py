"""Focused documentation-security regression tests."""
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[2] / 'scripts' / 'check_documentation_security.py'
spec = importlib.util.spec_from_file_location('doc_guard', SCRIPT)
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)


class DocumentationSecurityTests(unittest.TestCase):
    def test_secrets_and_safe_content(self):
        self.assertIn('github-token', guard.check(b'ghp_' + b'X' * 36))
        self.assertIn('private-key', guard.check(b'-----BEGIN PRIVATE KEY-----'))
        self.assertEqual(guard.check(b'# Public documentation\n'), [])

    def test_extensions(self):
        self.assertTrue(guard.is_doc('docs/guide.md'))
        self.assertTrue(guard.is_doc('AGENTS.md'))
        self.assertFalse(guard.is_doc('src/app.py'))

    def test_index_and_commit_range(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            def call(*args):
                return subprocess.run(args, cwd=root, capture_output=True, text=True, check=True).stdout
            call('git', 'init', '-q')
            call('git', 'config', 'user.name', 'Test')
            call('git', 'config', 'user.email', 'test@example.invalid')
            (root / 'AGENTS.md').write_text('# Safe\n')
            (root / 'README.md').write_text('# Safe\n')
            call('git', 'add', '.')
            call('git', 'commit', '-qm', 'baseline')
            base = call('git', 'rev-parse', 'HEAD').strip()
            secret = 'ghp_' + 'A' * 36
            (root / 'README.md').write_text(secret)
            p = subprocess.run(['python', str(SCRIPT)], cwd=root, capture_output=True, text=True)
            self.assertEqual(p.returncode, 0, p.stderr)
            call('git', 'add', 'README.md')
            p = subprocess.run(['python', str(SCRIPT)], cwd=root, capture_output=True, text=True)
            self.assertEqual(p.returncode, 1)
            self.assertIn('github-token', p.stderr)
            self.assertNotIn(secret, p.stderr)
            call('git', 'commit', '-qm', 'unsafe')
            p = subprocess.run(['python', str(SCRIPT), '--range', f'{base}..HEAD'],
                               cwd=root, capture_output=True, text=True)
            self.assertEqual(p.returncode, 1)


if __name__ == '__main__':
    unittest.main()
