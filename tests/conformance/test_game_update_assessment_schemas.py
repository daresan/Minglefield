"""Offline schema checks for P1.4f.3 release-bound declarations."""
import json
import sys
import unittest
from pathlib import Path
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]
SCHEMAS = ROOT / "schemas" / "integrations"
SOURCE = {"provider": "github", "repository": "alice/godot"}
BASE = {"integration_id": "community.alice.godot", "release_source": SOURCE,
        "from_version": "v1.0.0", "to_version": "v1.1.0"}


def validator(name):
    schema = json.loads((SCHEMAS / name).read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


class GameUpdateAssessmentSchemaTests(unittest.TestCase):
    def test_compatibility_contract(self):
        v = validator("game-update-compatibility-v0.1.schema.json")
        valid = {**BASE, "contract_version": "0.1",
                 "requirements": [{"capability": "game.api", "constraint": ">=1.0"}]}
        self.assertTrue(v.is_valid(valid))
        for bad in ({**valid, "unknown": True},
                    {**valid, "requirements": []},
                    {**valid, "release_source": {"provider": "github", "repository": "../bad"}},
                    {**valid, "to_version": ""}):
            with self.subTest(bad=bad):
                self.assertFalse(v.is_valid(bad))

    def test_repository_path_segments_are_not_navigation(self):
        for name in ("game-update-compatibility-v0.1.schema.json",
                     "game-update-migration-v0.1.schema.json"):
            with self.subTest(schema=name):
                v = validator(name)
                if "compatibility" in name:
                    valid = {**BASE, "contract_version": "0.1",
                             "requirements": [{"capability": "game.api", "constraint": ">=1"}]}
                else:
                    valid = {**BASE, "plan_version": "0.1",
                             "operations": [{"kind": "add", "path": "plugins/main.py"}],
                             "recovery": {"strategy": "restore_backup"}}
                for repository in ("../bad", "./bad", "owner/..", "owner/.",
                                   ".hidden/repo", "owner/.hidden", "owner//repo",
                                   "/repo", "owner/", "owner\\repo"):
                    with self.subTest(repository=repository):
                        bad = {**valid, "release_source":
                               {"provider": "github", "repository": repository}}
                        if repository in (".hidden/repo", "owner/.hidden"):
                            self.assertTrue(v.is_valid(bad))
                        else:
                            self.assertFalse(v.is_valid(bad))

    def test_migration_plan(self):
        v = validator("game-update-migration-v0.1.schema.json")
        valid = {**BASE, "plan_version": "0.1",
                 "operations": [{"kind": "replace", "path": "integrations/plugin.py"}],
                 "recovery": {"strategy": "restore_backup"}}
        self.assertTrue(v.is_valid(valid))
        for path in ("../escape", "safe/../../escape", "/absolute", "C:/absolute",
                     "folder\\escape"):
            with self.subTest(path=path):
                bad = {**valid, "operations": [{"kind": "replace", "path": path}]}
                self.assertFalse(v.is_valid(bad))
        self.assertFalse(v.is_valid({**valid, "recovery": {"strategy": "ignore"}}))
        self.assertFalse(v.is_valid({**valid, "operations": []}))


if __name__ == "__main__":
    unittest.main()
