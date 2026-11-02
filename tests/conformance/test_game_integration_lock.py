"""Conformance tests for the draft installation lock contract."""
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"server"))
from game_integration_lock import validate_integration_lock


def example():
    return {"lock_version":"0.1","project_id":"game.one","integrations":[{
        "integration_id":"community.alice.godot","installed_version":"1.2.3",
        "publisher":"alice",
        "release_source":{"provider":"github","repository":"alice/godot"},
        "artifact":{"reference":"release-asset-1","sha256":"a"*64},
        "source_revision":None,"verification_status":"unverified"}]}


class GameIntegrationLockTests(unittest.TestCase):
    def test_valid_record_and_explicit_empty_set(self):
        self.assertEqual(len(validate_integration_lock(example(),project_id="game.one")["integrations"]),1)
        empty=example()
        empty["integrations"]=[]
        self.assertEqual(validate_integration_lock(empty)["integrations"],[])

    def test_rejects_duplicate_and_wrong_project(self):
        record=example()
        with self.assertRaisesRegex(ValueError,"project_mismatch"):
            validate_integration_lock(record,project_id="game.two")
        record["integrations"].append(copy.deepcopy(record["integrations"][0]))
        with self.assertRaisesRegex(ValueError,"duplicate_integration_id"):
            validate_integration_lock(record)

    def test_rejects_invalid_digest_and_unexpected_fields(self):
        for field in ("digest","extra","provider"):
            record=example()
            if field=="digest":
                record["integrations"][0]["artifact"]["sha256"]="not-a-hash"
            elif field=="extra":
                record["integrations"][0]["secret"]="should-not-appear"
            else:
                record["integrations"][0]["release_source"]["provider"]="untrusted"
            with self.subTest(field=field),self.assertRaises(ValueError):
                validate_integration_lock(record)

    def test_status_is_declarative_not_verification(self):
        record=example()
        record["integrations"][0]["verification_status"]="verified"
        self.assertEqual(validate_integration_lock(record)["integrations"][0]["verification_status"],"verified")
        # Caller must not infer cryptographic trust from a user-editable status.


if __name__=="__main__":
    unittest.main()
