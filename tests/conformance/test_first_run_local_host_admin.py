"""Trusted offline, host-scoped first-run identity transaction conformance.

This is deliberately NOT a first-run authorization or HTTP gateway test:
the secure one-use local installer handoff remains a separate gate. All actual
writes below target disposable, already SQLCipher-encrypted test databases.
"""
import sqlite3
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "server"))
from alpha_sqlcipher_runtime import SQLITE_HEADER, sqlcipher_driver
from private_alpha_auth import AlphaAuthStore
from sec01_integrated_alpha_admission import IntegratedAlphaAdmission
from sec01_host_commit_policy_sim import HostCommitPolicy

DB_KEY = "Demo-Cipher-Local17!Key"
LOGIN_PASSWORD = "Separate-User-Password17!"
HOST = "host.local"
USER = "mingleadmin"


def sqlcipher_available():
    try:
        sqlcipher_driver()
        return True
    except Exception:
        return False


class PlaintextFailClosedTests(unittest.TestCase):
    def test_legacy_unencrypted_source_cannot_provision_initial_admin(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "legacy.db"
            store = AlphaAuthStore(path)
            policy = HostCommitPolicy(IntegratedAlphaAdmission(store))
            result = policy.provision_first_run_local_host_admin_trusted(
                HOST, LOGIN_PASSWORD
            )
            self.assertEqual((result.state, result.reason),
                             ("denied", "encrypted_destination_required"))
            with store._tx() as db:
                self.assertEqual(db.execute(
                    "SELECT count(*) FROM alpha_users").fetchone()[0], 0)
                self.assertEqual(db.execute(
                    "SELECT count(*) FROM sec01_host_owners").fetchone()[0], 0)
            self.assertEqual(path.read_bytes()[:16], SQLITE_HEADER)


@unittest.skipUnless(sqlcipher_available(), "real sqlcipher3 binary wheel unavailable")
class FirstRunEncryptedAdminTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="minglefield-local-first-run-")
        self.addCleanup(temp.cleanup)
        self.path = Path(temp.name) / "prepared-cipher-target.sqlite3"
        driver = sqlcipher_driver()
        db = driver.connect(str(self.path))
        db.execute("PRAGMA key = '" + DB_KEY.replace("'", "''") + "'")
        db.execute("CREATE TABLE encrypted_fixture (entry TEXT NOT NULL)")
        db.execute("INSERT INTO encrypted_fixture VALUES ('untouched')")
        db.commit()
        db.close()
        self.assertNotEqual(self.path.read_bytes()[:16], SQLITE_HEADER)
        self.store = AlphaAuthStore(
            self.path, sqlcipher_key_provider=lambda: DB_KEY)
        self.policy = HostCommitPolicy(IntegratedAlphaAdmission(self.store))

    def provision(self, host=HOST, password=LOGIN_PASSWORD, user=USER):
        return self.policy.provision_first_run_local_host_admin_trusted(
            host, password, login_user_id=user)

    def identities(self):
        with self.store._tx() as db:
            users = db.execute(
                "SELECT user_id FROM alpha_users ORDER BY user_id").fetchall()
            hosts = db.execute(
                "SELECT host_id,operator_id,active FROM alpha_executor_hosts"
                ).fetchall()
            owners = db.execute(
                "SELECT host_id,owner_id FROM sec01_host_owners").fetchall()
            passwords = db.execute(
                "SELECT user_id,salt,password_hash FROM alpha_passwords").fetchall()
            invites = db.execute(
                "SELECT count(*) FROM alpha_invites").fetchone()[0]
            sessions = db.execute(
                "SELECT count(*) FROM alpha_sessions").fetchone()[0]
            admins = db.execute(
                "SELECT count(*) FROM sec01_host_admins").fetchone()[0]
        return users, hosts, owners, passwords, invites, sessions, admins

    def test_no_invite_creates_login_owner_only_for_one_host(self):
        result = self.provision()
        self.assertEqual((result.state, result.reason),
                         ("created", "first_run_local_host_admin_created"))
        users, hosts, owners, passwords, invites, sessions, admins = self.identities()
        self.assertEqual(users, [(USER,)])
        self.assertEqual(hosts, [(HOST, USER, 1)])
        self.assertEqual(owners, [(HOST, USER)])
        self.assertEqual((invites, sessions, admins), (0, 0, 0))
        self.assertEqual(passwords[0][0], USER)
        self.assertEqual(len(passwords[0][1]), 16)
        self.assertEqual(len(passwords[0][2]), 32)
        self.assertNotEqual(passwords[0][2], LOGIN_PASSWORD.encode())
        self.assertNotIn(LOGIN_PASSWORD.encode(), self.path.read_bytes())
        self.assertNotIn(DB_KEY.encode(), self.path.read_bytes())
        session = self.store.login(USER, LOGIN_PASSWORD)
        self.assertIsNotNone(session)
        self.assertEqual(self.store.principal("Bearer "+session).user_id, USER)
        self.assertIsNone(self.store.login(USER, DB_KEY))
        self.assertEqual(len(self.policy.list_hosts(USER)), 1)
        self.assertEqual(self.policy.list_hosts(USER)[0]["host_id"], HOST)
        with self.store._tx() as db:
            self.assertTrue(self.policy._admin(db, HOST, USER))
            self.assertFalse(self.policy._admin(db, "host.remote", USER))
        self.assertNotEqual(self.path.read_bytes()[:16], SQLITE_HEADER)

    def test_custom_login_name_uses_same_host_scoped_authority(self):
        result = self.provision(user="local.operator")
        self.assertEqual(result.state, "created")
        self.assertIsNotNone(self.store.login("local.operator", LOGIN_PASSWORD))
        self.assertIsNone(self.store.login("mingleadmin", LOGIN_PASSWORD))
        self.assertEqual(self.policy.list_hosts("mingleadmin"), [])
        self.assertEqual(self.policy.list_hosts("local.operator")[0]["host_id"], HOST)

    def test_login_and_cipher_passwords_must_be_distinct(self):
        self.assertEqual(
            self.provision(password=DB_KEY).reason,
            "independent_login_password_required")
        self.assertEqual(
            self.provision(password="too-short").reason,
            "invalid_first_run_identity_or_password")
        self.assertEqual(
            self.provision(user="invalid/user").reason,
            "invalid_first_run_identity_or_password")
        self.assertEqual(
            self.provision(host="bad host").reason,
            "invalid_first_run_identity_or_password")
        self.assertEqual(self.identities()[0], [])

    def test_replay_is_denied_without_password_reset_or_role_expansion(self):
        self.assertEqual(self.provision().state, "created")
        before = self.identities()
        self.assertEqual(self.provision(password="Another-Valid-Password12!").reason,
                         "first_run_identity_conflict")
        self.assertEqual(self.provision(host="host.another").reason,
                         "first_run_identity_conflict")
        self.assertEqual(self.identities(), before)
        self.assertIsNotNone(self.store.login(USER, LOGIN_PASSWORD))
        self.assertIsNone(self.store.login(USER, "Another-Valid-Password12!"))

    def test_existing_migrated_account_is_not_overwritten(self):
        with self.store._tx() as db:
            db.execute("INSERT INTO alpha_users(user_id,disabled) VALUES(?,1)", (USER,))
        before = self.identities()
        self.assertEqual(self.provision().reason, "first_run_identity_conflict")
        self.assertEqual(self.identities(), before)

    def test_orphan_existing_host_admin_cannot_inherit_privileges(self):
        with self.store._tx() as db:
            db.execute(
                "INSERT INTO sec01_host_admins(host_id,admin_id) VALUES(?,?)",
                ("host.remote", USER))
        self.assertEqual(self.provision().reason, "first_run_identity_conflict")
        self.assertEqual(self.identities()[0], [])

    def test_host_conflict_does_not_steal_existing_operator(self):
        with self.store._tx() as db:
            db.execute(
                "INSERT INTO alpha_executor_hosts VALUES(?,?,1)",
                (HOST, "another.operator"))
        self.assertEqual(self.provision().reason, "first_run_host_conflict")
        self.assertEqual(self.identities()[0], [])
        self.assertEqual(self.identities()[1], [(HOST, "another.operator", 1)])

    def test_orphan_host_references_deny_silent_reassignment(self):
        with self.store._tx() as db:
            db.execute(
                "INSERT INTO sec01_host_owners VALUES(?,?)",
                (HOST, "other.user"))
        self.assertEqual(self.provision().reason, "first_run_host_conflict")
        self.assertEqual(self.identities()[0], [])

    def test_aborted_owner_insert_rolls_back_user_password_and_host(self):
        with self.store._tx() as db:
            db.execute("""CREATE TRIGGER test_abort_first_run
                BEFORE INSERT ON sec01_host_owners
                BEGIN SELECT RAISE(ABORT,'simulated_failure'); END""")
        with self.assertRaises(Exception):
            self.provision()
        users, hosts, owners, passwords, _, _, _ = self.identities()
        self.assertEqual((users, hosts, owners, passwords), ([], [], [], []))
        with self.store._tx() as db:
            db.execute("DROP TRIGGER test_abort_first_run")
        self.assertEqual(self.provision().state, "created")

    def test_concurrent_first_run_only_one_owner(self):
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _:self.provision().state, [0,1]))
        self.assertEqual(sorted(results), ["created", "denied"])
        self.assertEqual(self.identities()[0], [(USER,)])
        self.assertEqual(self.identities()[2], [(HOST, USER)])


if __name__ == "__main__":
    unittest.main()
