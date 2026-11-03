import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"server"))
from game_integration_updates import discover_integration_update
from game_integration_assessment import assess_compatibility, assess_migration

SOURCE={"provider":"github","repository":"alice/godot"}
ENTRY={"integration_id":"community.alice.godot","declared_version":"1.2.3",
       "release_source":SOURCE,"source_state":"registry_match"}
CATALOG={"state":"available","integrations":[{"integration_id":"community.alice.godot",
         "publisher":"alice","release_source":SOURCE}]}


def releases(repo):
    assert repo=="alice/godot"
    return {"state":"available","releases":[
        {"tag_name":"v1.3.0","release_notes":"Upgrade","release_url":"https://github.com/alice/godot/releases/tag/v1.3.0"},
        {"tag_name":"v2.0.0rc1","prerelease":True},
        {"tag_name":"not-a-version"}]}


class GameIntegrationUpdateTests(unittest.TestCase):
    def test_update_preview_uses_registry_source(self):
        report=discover_integration_update(ENTRY,CATALOG,fetcher=releases,
            compare_fetcher=lambda *_: {"state":"unknown"})
        self.assertEqual(report["state"],"unknown")
        self.assertEqual(report["available_version"],"v1.3.0")
        self.assertEqual(report["release_notes"],"Upgrade")
        self.assertEqual(report["verification_state"],"unknown")
        preview=report["preview"]
        self.assertEqual(preview["state"],"incomplete")
        self.assertEqual(preview["release_notes"],"Upgrade")
        self.assertEqual(preview["changed_files"],{"state":"unknown","files":[],
                         "comparison_url":"https://github.com/alice/godot/compare/1.2.3...v1.3.0"})
        self.assertEqual(preview["compatibility"], assess_compatibility())
        self.assertEqual(preview["migration"], assess_migration())
        self.assertEqual(preview["compatibility"]["state"],"unknown")
        self.assertEqual(preview["compatibility"]["reason"],"no_verified_compatibility_contract")
        self.assertIs(preview["compatibility"]["requires_manual_review"],True)
        self.assertEqual(preview["migration"]["state"],"unknown")
        self.assertEqual(preview["migration"]["reason"],"no_verified_migration_plan")
        self.assertIs(preview["migration"]["requires_manual_review"],True)
        self.assertEqual(preview["artifact_integrity"]["state"],"unknown")
        self.assertIs(preview["installation_allowed"],False)
        verified=discover_integration_update(ENTRY,CATALOG,fetcher=releases,
            compare_fetcher=lambda *_: {"state":"available","files":[{"path":"plugin.py","status":"modified"}]})
        self.assertEqual(verified["preview"]["changed_files"]["state"],"available")
        self.assertEqual(verified["preview"]["changed_files"]["files"][0]["path"],"plugin.py")
        self.assertIs(verified["preview"]["installation_allowed"],False)

    def test_up_to_date_and_no_comparable_releases(self):
        entry=dict(ENTRY,declared_version="1.3.0")
        current=discover_integration_update(entry,CATALOG,fetcher=releases,
            compare_fetcher=lambda *_: {"state":"unknown"})
        self.assertEqual(current["state"],"unknown")
        self.assertIsNone(current["preview"]["changed_files"]["comparison_url"])
        self.assertEqual(discover_integration_update(ENTRY,CATALOG,fetcher=lambda _:{"state":"available","releases":[]})["state"],"unknown")

    def test_source_mismatch_and_missing_registry_fail_closed(self):
        entry=dict(ENTRY,source_state="source_mismatch")
        self.assertEqual(discover_integration_update(entry,CATALOG,fetcher=releases)["reason"],"untrusted_source")
        self.assertEqual(discover_integration_update(ENTRY,{"state":"unavailable"},fetcher=releases)["state"],"unknown")
        self.assertEqual(discover_integration_update(ENTRY,{"state":"available","integrations":[]},fetcher=releases)["state"],"unknown")

    def test_malformed_adapter_and_registry_data_fail_closed(self):
        for payload in (None, [], "invalid", {"state":"available"},
                        {"state":"available","releases":None},
                        {"state":"available","releases":[None]}):
            with self.subTest(payload=payload):
                result=discover_integration_update(ENTRY,CATALOG,fetcher=lambda _,p=payload:p)
                self.assertEqual(result["state"],"unknown")
        for integrations in (None, {}, [None]):
            with self.subTest(integrations=integrations):
                catalog={"state":"available","integrations":integrations}
                result=discover_integration_update(ENTRY,catalog,fetcher=releases)
                self.assertEqual(result["state"],"unknown")

    def test_offline_and_invalid_versions_remain_unknown(self):
        self.assertEqual(discover_integration_update(ENTRY,CATALOG,fetcher=lambda _:{"state":"unavailable"})["state"],"unknown")
        self.assertEqual(discover_integration_update(dict(ENTRY,declared_version="n/a"),CATALOG,fetcher=releases)["state"],"unknown")
        self.assertEqual(discover_integration_update(ENTRY,CATALOG,fetcher=lambda _: (_ for _ in ()).throw(OSError()))["state"],"unknown")

    def test_explicit_comparison_states_and_pep440_policy(self):
        for declared, tag, expected in [
            ("1.2", "v1.2.0", "up_to_date"),
            ("1.9", "1.10", "update_available"),
            ("2.0", "1.9", "up_to_date"),
            ("1.0", "1.0.post1", "update_available"),
            ("1.0+build", "2.0", "unknown"),
            ("1.0rc1", "2.0", "unknown"),
            ("1.0", "2.0+build", "unknown"),
            ("1.0", "2.0.dev1", "unknown"),
            ("1.0", "2.0rc1", "unknown")]:
            with self.subTest(declared=declared, tag=tag):
                result=discover_integration_update(dict(ENTRY,declared_version=declared),
                    CATALOG,fetcher=lambda _: {"state":"available","releases":[{"tag_name":tag}]},
                    compare_fetcher=lambda *_: {"state":"unknown"})
                self.assertEqual(result["comparison_state"],expected)
                self.assertEqual(result["state"],"unknown")
                self.assertFalse(result["installation_allowed"])
                self.assertEqual(result["version_scheme"],"pep440")

    def test_errors_are_distinct_from_unknown_and_current(self):
        for payload in ({"state":"unavailable"}, {"state":"available","releases":[None]}):
            result=discover_integration_update(ENTRY,CATALOG,fetcher=lambda _: payload)
            self.assertEqual(result["comparison_state"],"error")
        result=discover_integration_update(ENTRY,CATALOG,
            fetcher=lambda _: {"state":"available","complete":False,"releases":[{"tag_name":"1.2.3"}]})
        self.assertEqual(result["comparison_state"],"unknown")


if __name__=="__main__":
    unittest.main()
