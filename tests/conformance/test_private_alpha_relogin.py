"""Private Alpha v4 repeat login and legacy account migration tests."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"server"))
from private_alpha_auth import AlphaAuthStore

class AlphaReloginTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.now=10000
        self.db=Path(tmp.name)/"relogin.sqlite"
        self.store=AlphaAuthStore(self.db,clock=lambda:self.now)

    def test_relogin_after_session_expiry_without_new_invite(self):
        first=self.store.redeem(self.store.invite("user.alpha"),
            agent_id="agent.alpha",password="passphrase-test-123456")
        self.assertIsNotNone(first)
        p=self.store.principal("Bearer "+first)
        self.assertEqual(self.store.submit(p,
            {"action":"demo.echo","idempotency_key":"first"})[0],201)
        self.now+=901
        self.assertIsNone(self.store.principal("Bearer "+first))
        fresh=AlphaAuthStore(self.db,clock=lambda:self.now).login(
            "user.alpha","passphrase-test-123456")
        self.assertIsNotNone(fresh)
        principal=self.store.principal("Bearer "+fresh)
        self.assertEqual(principal.agent_id,"agent.alpha")
        self.assertEqual(len(self.store.jobs(principal)),1)

    def test_wrong_password_disabled_user_and_minimum_length(self):
        invite=self.store.invite("user.alpha")
        self.assertIsNone(self.store.redeem(invite,agent_id="agent.alpha",password="short"))
        self.assertIsNotNone(self.store.redeem(invite,agent_id="agent.alpha",
                                               password="passphrase-test-123456"))
        self.assertIsNone(self.store.login("user.alpha","incorrect-password-12"))
        self.assertTrue(self.store.disable_user("user.alpha"))
        self.assertIsNone(self.store.login("user.alpha","passphrase-test-123456"))

    def test_legacy_user_can_set_password_with_active_session(self):
        old=self.store.redeem(self.store.invite("user.legacy"),agent_id="agent.legacy")
        self.assertIsNone(self.store.login("user.legacy","passphrase-test-123456"))
        self.assertTrue(self.store.set_password_authenticated(
            "Bearer "+old,"passphrase-test-123456"))
        self.now+=901
        self.assertIsNone(self.store.principal("Bearer "+old))
        self.assertIsNotNone(self.store.login("user.legacy","passphrase-test-123456"))

    def test_expired_session_cannot_set_legacy_password(self):
        old=self.store.redeem(self.store.invite("user.legacy"),agent_id="agent.legacy")
        self.now+=901
        self.assertFalse(self.store.set_password_authenticated(
            "Bearer "+old,"passphrase-test-123456"))
        self.assertIsNone(self.store.login("user.legacy","passphrase-test-123456"))

    def test_local_operator_recovery_preserves_legacy_agent_and_jobs(self):
        old=self.store.redeem(self.store.invite("user.legacy"),agent_id="agent.legacy")
        principal=self.store.principal("Bearer "+old)
        self.assertEqual(self.store.submit(principal,
            {"action":"demo.echo","idempotency_key":"first"})[0],201)
        self.now+=901
        self.assertTrue(self.store.operator_reset_password(
            "user.legacy","new-test-password-123"))
        self.assertIsNone(self.store.principal("Bearer "+old))
        fresh=self.store.login("user.legacy","new-test-password-123")
        self.assertIsNotNone(fresh)
        p=self.store.principal("Bearer "+fresh)
        self.assertEqual(p.agent_id,"agent.legacy")
        self.assertEqual(len(self.store.jobs(p)),1)
        self.assertFalse(self.store.operator_reset_password(
            "user.missing","new-test-password-123"))

    def test_existing_password_is_not_stored_in_plaintext(self):
        self.store.redeem(self.store.invite("user.alpha"),agent_id="agent.alpha",
                          password="passphrase-test-123456")
        import sqlite3
        with sqlite3.connect(self.db) as db:
            row=db.execute("SELECT salt,password_hash FROM alpha_passwords").fetchone()
        self.assertEqual(len(row[0]),16)
        self.assertEqual(len(row[1]),32)
        self.assertNotIn(b"passphrase-test-123456",row[1])

if __name__=="__main__":
    unittest.main()
