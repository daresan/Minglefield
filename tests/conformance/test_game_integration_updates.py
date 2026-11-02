import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"server"))
from game_integration_updates import discover_integration_update

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
        report=discover_integration_update(ENTRY,CATALOG,fetcher=releases)
        self.assertEqual(report["state"],"update_available")
        self.assertEqual(report["available_version"],"v1.3.0")
        self.assertEqual(report["release_notes"],"Upgrade")
        self.assertEqual(report["verification_state"],"unknown")

    def test_up_to_date_and_no_comparable_releases(self):
        entry=dict(ENTRY,declared_version="1.3.0")
        self.assertEqual(discover_integration_update(entry,CATALOG,fetcher=releases)["state"],"up_to_date")
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


if __name__=="__main__":
    unittest.main()
