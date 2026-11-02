"""Draft unified package lock format tests."""
import copy
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"server"))
from game_package_lock import validate_package_lock,lock_source_state


def sample():
    return {"lock_version":"0.1","project_id":"game.one","packages":[{
        "package_id":"community.alice.godot","kind":"game_integration",
        "version":"1.2.3","publisher":"alice",
        "release_source":{"provider":"github","repository":"alice/godot"},
        "artifact":{"reference":"asset-1","sha256":"a"*64}}]}


class GamePackageLockTests(unittest.TestCase):
    def test_valid_and_explicit_empty_declarations(self):
        self.assertEqual(len(validate_package_lock(sample(),project_id="game.one")["packages"]),1)
        value=sample()
        value["packages"]=[]
        self.assertEqual(validate_package_lock(value)["packages"],[])

    def test_project_and_duplicate_rejected(self):
        with self.assertRaisesRegex(ValueError,"project_mismatch"):
            validate_package_lock(sample(),project_id="game.other")
        value=sample()
        value["packages"].append(copy.deepcopy(value["packages"][0]))
        with self.assertRaisesRegex(ValueError,"duplicate_package_id"):
            validate_package_lock(value)

    def test_malformed_source_digest_and_unknown_kind_rejected(self):
        for field in ("digest","source","kind","extra"):
            value=sample()
            item=value["packages"][0]
            if field=="digest":
                item["artifact"]["sha256"]="invalid"
            elif field=="source":
                item["release_source"]["repository"]="https://example.com"
            elif field=="kind":
                item["kind"]="agent"
            else:
                item["verification_status"]="verified"
            with self.subTest(field=field),self.assertRaises(ValueError):
                validate_package_lock(value)

    def test_no_silent_precedence_between_lockfiles(self):
        self.assertEqual(lock_source_state(alpha_exists=False,root_exists=False),"installation_unknown")
        self.assertEqual(lock_source_state(alpha_exists=True,root_exists=False),"legacy_alpha_lock")
        self.assertEqual(lock_source_state(alpha_exists=False,root_exists=True),"unified_lock_declared")
        self.assertEqual(lock_source_state(alpha_exists=True,root_exists=True),"conflicting_lock_sources")


if __name__=="__main__":
    unittest.main()
