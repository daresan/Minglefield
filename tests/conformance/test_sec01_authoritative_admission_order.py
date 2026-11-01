"""SEC-01 isolation: authoritative same-database admission/revocation ordering.

This shows the serialization property that a future remote service needs.
It does NOT model network authentication or a real game's effect transaction.
"""
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"server"))
from sec01_authority_fencing_sqlite import SQLiteAuthorityFence

IDS=("session.one","grant.one","agent.one","principal.one")

class AuthoritativeAdmissionOrderTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.db=Path(tmp.name)/"fence.db"
        self.fence=SQLiteAuthorityFence(self.db)
        self.fence.provision(IDS)

    def test_revocation_committed_first_blocks_admission(self):
        original=self.fence.snapshot(IDS)
        self.fence.invalidate("session",IDS[0])
        denied=self.fence.accept(snapshot=original,effect_key="effect.one",
                                  binding=("job.one","fingerprint.one"))
        self.assertEqual(denied.reason,"authority_revoked_or_changed")
        self.assertEqual(self.fence.accepted_count(),0)

    def test_admission_committed_first_is_historical_after_revoke(self):
        snapshot=self.fence.snapshot(IDS)
        first=self.fence.accept(snapshot=snapshot,effect_key="effect.one",
                                binding=("job.one","fingerprint.one"))
        self.assertEqual(first.reason,"accepted_once")
        self.fence.invalidate("session",IDS[0])
        again=self.fence.accept(snapshot=snapshot,effect_key="effect.one",
                                binding=("job.one","fingerprint.one"))
        self.assertEqual(again.reason,"already_accepted_no_new_effect")
        self.assertEqual(self.fence.accepted_count(),1)

    def test_concurrent_revoke_and_accept_share_serial_order(self):
        snapshot=self.fence.snapshot(IDS)
        def accept():
            return SQLiteAuthorityFence(self.db).accept(
                snapshot=snapshot,effect_key="effect.one",
                binding=("job.one","fingerprint.one")).reason
        def revoke():
            SQLiteAuthorityFence(self.db).invalidate("session",IDS[0])
        with ThreadPoolExecutor(max_workers=2) as executor:
            acceptance=executor.submit(accept)
            invalidation=executor.submit(revoke)
            outcome=acceptance.result()
            invalidation.result()
        self.assertIn(outcome,("accepted_once","authority_revoked_or_changed"))
        self.assertEqual(self.fence.accepted_count(),
                         1 if outcome=="accepted_once" else 0)
        if outcome=="accepted_once":
            self.assertEqual(self.fence.accept(
                snapshot=snapshot,effect_key="effect.one",
                binding=("job.one","fingerprint.one")).reason,
                "already_accepted_no_new_effect")

if __name__=="__main__":
    unittest.main()
