import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "server"))

from action_service import _canonical


class UnicodeBoundaryTests(unittest.TestCase):
    def test_reject_isolated_surrogate_in_value(self):
        with self.assertRaises(ValueError):
            _canonical({"text": chr(0xD800)})

    def test_reject_isolated_surrogate_in_key(self):
        with self.assertRaises(ValueError):
            _canonical({chr(0xDFFF): "value"})

    def test_accept_valid_unicode(self):
        encoded = _canonical({"text": "Grüße 🌍"})
        self.assertIn("text", encoded)


if __name__ == "__main__":
    unittest.main()
