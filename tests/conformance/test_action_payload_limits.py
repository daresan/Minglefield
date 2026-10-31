"""B1 parameter boundary tests; no database effects on invalid requests."""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "server"))
from action_service import _canonical

# Reuse the real authenticated SQLite fixture, not a mocked submission path.
from test_action_submission import SubmissionTests


class PayloadBoundaryTests(SubmissionTests):
    """Use existing fixture helpers; inherited submission tests also run here."""

    def test_canonical_ascii_bytes_match_character_length(self):
        for payload in ({"x": "🌍"}, {"nested": ["é", "\\", "\n"]}):
            encoded = _canonical(payload)
            self.assertEqual(len(encoded), len(encoded.encode("utf-8")))
            self.assertEqual(json.loads(encoded), payload)

    def test_exact_64k_boundary_and_one_byte_over(self):
        prefix = len(_canonical({"x": ""}))
        accepted = {"x": "a" * (65536 - prefix)}
        denied = {"x": "a" * (65537 - prefix)}
        self.assertEqual(len(_canonical(accepted)), 65536)
        self.assertEqual(len(_canonical(denied)), 65537)
        self.assertEqual(self.service.submit(**(self.args | dict(parameters=denied))).reason,
                         "invalid_request")
        self.assertEqual(self.counts(), (0, 0, 0))
        result = self.service.submit(**(self.args | dict(parameters=accepted)))
        self.assertTrue(result.allowed)
        self.assertEqual(self.counts(), (1, 1, 100))

    def test_oversize_unicode_escape_denied_without_reservation(self):
        # Non-BMP code points use 12 ASCII bytes in ensure_ascii JSON encoding.
        payload = {"x": "🌍" * 6000}
        self.assertGreater(len(_canonical(payload)), 65536)
        result = self.service.submit(**(self.args | dict(parameters=payload)))
        self.assertEqual(result.reason, "invalid_request")
        self.assertEqual(self.counts(), (0, 0, 0))

    def test_deep_nesting_denied_without_reservation(self):
        nested = "leaf"
        for _ in range(1200):
            nested = [nested]
        result = self.service.submit(**(self.args | dict(parameters={"x": nested})))
        self.assertEqual(result.reason, "invalid_request")
        self.assertEqual(self.counts(), (0, 0, 0))


if __name__ == "__main__":
    unittest.main()
